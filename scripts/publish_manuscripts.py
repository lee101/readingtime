from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "manuscripts" / "ethics-covers.json"
DEFAULT_DB = ROOT / "readingtime.db"
DEFAULT_STATIC_ROOT = ROOT / "static"
EDITORIAL_USER_ID = "readingtime-editorial"
LEVELS = {"accessible", "intermediate", "advanced"}
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
COVER_RE = re.compile(r"!\[Cover art:\s*([^\]\r\n]+)\]\(([^)\r\n]+)\)")
INFOGRAPHIC_RE = re.compile(r"!\[Infographic:\s*([^\]\r\n]+)\]\(([^)\r\n]+)\)")
SEPARATOR_RE = re.compile(r"^\*[\t ]+\*[\t ]+\*[\t ]*$")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
WORDS_PER_MINUTE = 140
# The stories table, in the order both backends insert. Postgres is the live
# database; readingtime.db is the SQLite file the Go app imported it from, and
# both carry the same column names.
STORY_COLUMNS = (
    "id", "user_id", "author_name", "title", "prompt", "cover_url", "text_model",
    "image_model", "public", "pages_json", "word_count", "reading_minutes",
    "created_at", "updated_at",
)


@dataclass(frozen=True)
class StoryRecord:
    story_id: str
    title: str
    audience: str
    level: str
    prompt: str
    cover_source: Path
    cover_target: Path
    cover_url: str
    infographic_source: Path | None
    infographic_target: Path | None
    infographic_url: str | None
    pages: list[dict[str, Any]]
    word_count: int
    reading_minutes: int


@dataclass(frozen=True)
class StagedCover:
    target: Path
    temporary: Path
    previous: bytes | None

def repo_path(raw_path: str | Path, label: str, *, must_exist: bool = False) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise ValueError(f"{label} cannot be resolved: {exc}") from exc
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{label} must be under {ROOT}") from exc
    return resolved


def manifest_path(raw_path: str, label: str) -> tuple[str, Path]:
    relative = PurePosixPath(raw_path.replace("\\", "/"))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"{label} must be a safe repository-relative path")
    normalized = relative.as_posix()
    return normalized, repo_path(normalized, label, must_exist=True)


def linked_cover_path(raw_path: str, source: Path) -> Path:
    path = Path(raw_path.replace("\\", "/"))
    if path.is_absolute():
        raise ValueError(f"{source} cover link must be local")
    try:
        resolved = (source.parent / path).resolve(strict=True)
        resolved.relative_to(ROOT)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{source} cover link must resolve under {ROOT}: {exc}") from exc
    return resolved


def text_value(item: dict[str, Any], key: str, label: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def reading_minutes(words: int) -> int:
    """Whole-minute reading estimate. Mirrors the Go reader's 140 wpm rate."""
    return max(1, -(-words // WORDS_PER_MINUTE))


def strip_emphasis(text: str) -> str:
    text = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", text, flags=re.DOTALL)
    return re.sub(r"(?<!\w)([*_])(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", text, flags=re.DOTALL)


def split_paragraph(paragraph: str, target_words: int) -> list[str]:
    if word_count(paragraph) <= target_words:
        return [paragraph]
    sentences = [
        match.group(0).strip()
        for match in re.finditer(r".+?(?:[.!?…][”’\"]?(?=\s|$)|$)", paragraph, flags=re.DOTALL)
        if match.group(0).strip()
    ]
    if not sentences:
        sentences = [paragraph]
    units: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= target_words:
            units.append(sentence)
        else:
            units.extend(" ".join(words[index : index + target_words]) for index in range(0, len(words), target_words))
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for unit in units:
        unit_words = word_count(unit)
        if current and current_words + unit_words > target_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(unit)
        current_words += unit_words
        if current_words >= target_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def split_scene(
    paragraphs: list[str],
    target_words: int,
    first_target_words: int | None = None,
) -> list[list[str]]:
    if not paragraphs:
        raise ValueError("empty scene")
    units: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        limit = first_target_words if index == 0 and first_target_words else target_words
        units.extend(split_paragraph(paragraph, limit))
    pages: list[list[str]] = []
    current: list[str] = []
    current_words = 0
    page_limit = first_target_words or target_words
    for unit in units:
        unit_words = word_count(unit)
        if current and current_words + unit_words > page_limit:
            pages.append(current)
            current = []
            current_words = 0
            page_limit = target_words
        current.append(unit)
        current_words += unit_words
        if current_words >= page_limit:
            pages.append(current)
            current = []
            current_words = 0
            page_limit = target_words
    if current:
        pages.append(current)
    if len(pages) > 1:
        previous_words = sum(word_count(paragraph) for paragraph in pages[-2])
        final_words = sum(word_count(paragraph) for paragraph in pages[-1])
        if final_words * 3 < previous_words:
            pages[-2].extend(pages.pop())
    return pages


def split_scenes(scenes: list[list[str]], target_words: int) -> list[str]:
    pages: list[list[str]] = []
    for index, paragraphs in enumerate(scenes):
        pages.extend(split_scene(paragraphs, target_words))
    while len(pages) > 30:
        index = min(
            range(len(pages) - 1),
            key=lambda i: (word_count("\n\n".join(pages[i] + pages[i + 1])), i),
        )
        pages[index : index + 2] = [pages[index] + pages[index + 1]]
    while len(pages) < 3:
        candidates = [i for i, paragraphs in enumerate(pages) if len(paragraphs) > 1]
        if not candidates:
            break
        index = max(candidates, key=lambda i: (word_count("\n\n".join(pages[i])), -i))
        paragraphs = pages[index]
        split_at = min(
            range(1, len(paragraphs)),
            key=lambda i: abs(
                word_count("\n\n".join(paragraphs[:i])) - word_count("\n\n".join(paragraphs[i:]))
            ),
        )
        pages[index : index + 1] = [paragraphs[:split_at], paragraphs[split_at:]]
    if not 3 <= len(pages) <= 30:
        raise ValueError(f"story must produce 3–30 text pages, produced {len(pages)}")
    return ["\n\n".join(paragraphs) for paragraphs in pages]


def parse_manuscript(
    source: Path,
    title: str,
    level: str,
    cover_url: str,
    target_words: int,
    infographic_url: str | None = None,
) -> list[dict[str, Any]]:
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {source}: {exc}") from exc
    h1_indexes = [index for index, line in enumerate(lines) if H1_RE.fullmatch(line)]
    if len(h1_indexes) != 1:
        raise ValueError(f"{source} must contain exactly one H1")
    h1_index = h1_indexes[0]
    if next((index for index, line in enumerate(lines) if line.strip()), h1_index) != h1_index:
        raise ValueError(f"{source} H1 must be the first content line")
    manuscript_title = H1_RE.fullmatch(lines[h1_index]).group(1).strip()
    if manuscript_title != title:
        raise ValueError(f"{source} H1 does not match manifest title")
    image_index = h1_index + 1
    while image_index < len(lines) and not lines[image_index].strip():
        image_index += 1
    if image_index >= len(lines):
        raise ValueError(f"{source} is missing its immediate cover link")
    cover_match = COVER_RE.fullmatch(lines[image_index].strip())
    if cover_match is None:
        raise ValueError(f"{source} must immediately follow its H1 with a cover link")
    alt_text, linked_cover = cover_match.groups()
    if alt_text.strip() != title:
        raise ValueError(f"{source} cover alt text does not match its title")
    expected_cover = repo_path(
        source.parent.parent / "art" / level / f"{source.stem}.webp",
        f"{source} cover",
        must_exist=True,
    )
    linked_path = linked_cover_path(linked_cover.strip(), source)
    if linked_path != expected_cover:
        raise ValueError(f"{source} cover link does not match its level and stem")
    if source.parent.name != level:
        raise ValueError(f"{source} level directory does not match {level}")
    infographic_index = image_index + 1
    while infographic_index < len(lines) and not lines[infographic_index].strip():
        infographic_index += 1
    infographic_match = None
    if infographic_index < len(lines):
        infographic_match = INFOGRAPHIC_RE.fullmatch(lines[infographic_index].strip())
    if infographic_url is not None:
        if infographic_match is None:
            raise ValueError(f"{source} must immediately follow its cover with an infographic link")
        infographic_alt, linked_infographic = infographic_match.groups()
        if infographic_alt.strip() != title:
            raise ValueError(f"{source} infographic alt text does not match its title")
        expected_infographic = repo_path(
            source.parent.parent / "infographics" / level / f"{source.stem}.svg",
            f"{source} infographic",
            must_exist=True,
        )
        if linked_cover_path(linked_infographic.strip(), source) != expected_infographic:
            raise ValueError(f"{source} infographic link does not match its level and stem")
    elif infographic_match is not None:
        raise ValueError(f"{source} infographic link requires a manifest field")
    else:
        infographic_index = -1

    scenes: list[list[str]] = [[]]
    paragraph_lines: list[str] = []

    def finish_paragraph() -> None:
        if paragraph_lines:
            paragraph = strip_emphasis(" ".join(paragraph_lines).strip())
            if not paragraph:
                raise ValueError(f"{source} contains an empty paragraph")
            scenes[-1].append(paragraph)
            paragraph_lines.clear()

    for index, line in enumerate(lines):
        if index in {h1_index, image_index, infographic_index}:
            continue
        if SEPARATOR_RE.fullmatch(line):
            finish_paragraph()
            if not scenes[-1]:
                raise ValueError(f"{source} contains an empty scene")
            scenes.append([])
            continue
        if not line.strip():
            finish_paragraph()
        else:
            paragraph_lines.append(line.strip())
    finish_paragraph()
    if not scenes[-1]:
        raise ValueError(f"{source} contains an empty scene")
    if not any(scenes):
        raise ValueError(f"{source} contains no story text")

    page_texts = split_scenes(scenes, target_words)
    page_texts.insert(0, "")
    pages: list[dict[str, Any]] = [
        {"text": page_text, "words": []} for page_text in page_texts
    ]
    pages[0]["image_url"] = cover_url
    if infographic_url is not None:
        pages[-1]["image_url"] = infographic_url
    return pages


def load_records(manifest: Path, static_root: Path) -> list[StoryRecord]:
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {manifest}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("covers"), list):
        raise ValueError("manifest must contain a covers array")
    records: list[StoryRecord] = []
    seen_paths: set[str] = set()
    seen_targets: set[str] = set()
    seen_ids: set[str] = set()
    for index, item in enumerate(document["covers"], 1):
        label = f"covers[{index - 1}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        relative_manuscript, source = manifest_path(text_value(item, "path", label), f"{label}.path")
        if source.suffix.lower() != ".md":
            raise ValueError(f"{label}.path must identify a Markdown file")
        if relative_manuscript in seen_paths:
            raise ValueError(f"duplicate manuscript path: {relative_manuscript}")
        seen_paths.add(relative_manuscript)
        title = text_value(item, "title", label)
        level = text_value(item, "level", label)
        if level not in LEVELS:
            raise ValueError(f"{label}.level must be accessible, intermediate, or advanced")
        audience = text_value(item, "audience", label)
        text_value(item, "prompt", label)
        infographic_source = None
        infographic_target = None
        infographic_url = None
        infographic_value = item.get("infographic")
        if infographic_value is not None:
            if not isinstance(infographic_value, str) or not infographic_value.strip():
                raise ValueError(f"{label}.infographic must be a non-empty path")
            _, infographic_source = manifest_path(infographic_value.strip(), f"{label}.infographic")
            expected_infographic = repo_path(
                source.parent.parent / "infographics" / level / f"{source.stem}.svg",
                f"{label} infographic source",
                must_exist=True,
            )
            if infographic_source != expected_infographic:
                raise ValueError(f"{label}.infographic does not match its level and stem")
            infographic_filename = f"{source.stem}.svg"
            infographic_target = repo_path(
                static_root / "educational-infographics" / level / infographic_filename,
                f"{label} infographic target",
            )
            infographic_url = f"/static/educational-infographics/{level}/{infographic_filename}"
        target_words = item.get("target_words")
        if isinstance(target_words, bool) or not isinstance(target_words, int) or target_words <= 0:
            raise ValueError(f"{label}.target_words must be a positive integer")
        filename = f"{source.stem}.webp"
        cover_target = repo_path(
            static_root / "manuscript-covers" / level / filename,
            f"{label} cover target",
        )
        cover_key = str(cover_target)
        if cover_key in seen_targets:
            raise ValueError(f"duplicate cover target: {cover_key}")
        seen_targets.add(cover_key)
        cover_url = f"/static/manuscript-covers/{level}/{filename}"
        if infographic_target is not None:
            infographic_key = str(infographic_target)
            if infographic_key in seen_targets:
                raise ValueError(f"duplicate infographic target: {infographic_key}")
            seen_targets.add(infographic_key)
        story_id = "rt-" + hashlib.sha256(relative_manuscript.encode("utf-8")).hexdigest()[:20]
        if story_id in seen_ids:
            raise ValueError(f"deterministic story ID collision: {story_id}")
        seen_ids.add(story_id)
        prompt = f"Original story; level: {level}; audience: {audience}."
        pages = parse_manuscript(source, title, level, cover_url, target_words, infographic_url)
        expected_cover = repo_path(
            source.parent.parent / "art" / level / filename,
            f"{label} cover",
            must_exist=True,
        )
        words = sum(word_count(str(page["text"])) for page in pages)
        records.append(
            StoryRecord(
                story_id=story_id,
                title=title,
                audience=audience,
                level=level,
                prompt=prompt,
                cover_source=expected_cover,
                cover_target=cover_target,
                infographic_source=infographic_source,
                infographic_target=infographic_target,
                infographic_url=infographic_url,
                cover_url=cover_url,
                pages=pages,
                word_count=words,
                reading_minutes=reading_minutes(words),
            )
        )
    if not records:
        raise ValueError("manifest contains no covers")
    return records


def stage_cover(source: Path, target: Path) -> StagedCover:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.parent.resolve().relative_to(ROOT)
        previous = target.read_bytes() if target.exists() else None
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot prepare cover target {target}: {exc}") from exc
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"cannot stage cover {source} for {target}: {exc}") from exc
    return StagedCover(target=target, temporary=temporary, previous=previous)


def write_atomic(target: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, target)
    except OSError as exc:
        raise ValueError(f"cannot restore cover {target}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def restore_covers(covers: list[StagedCover]) -> None:
    errors: list[str] = []
    for cover in reversed(covers):
        try:
            if cover.previous is None:
                cover.target.unlink(missing_ok=True)
            else:
                write_atomic(cover.target, cover.previous)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("; ".join(errors))


def replace_staged(covers: list[StagedCover]) -> list[StagedCover]:
    replaced: list[StagedCover] = []
    try:
        for cover in covers:
            os.replace(cover.temporary, cover.target)
            replaced.append(cover)
    except OSError as exc:
        restore_covers(replaced)
        raise ValueError(f"cannot replace staged covers: {exc}") from exc
    return replaced


def backup_database(db_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = repo_path(
        db_path.with_name(f"{db_path.name}-{timestamp}.bak"),
        "database backup",
    )
    source = sqlite3.connect(db_path, timeout=5)
    backup: sqlite3.Connection | None = None
    try:
        backup = sqlite3.connect(destination)
        source.backup(backup)
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        raise ValueError(f"database backup failed: {exc}") from exc
    finally:
        if backup is not None:
            backup.close()
        source.close()
    return destination


def check_schema(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(stories)")}
    if not columns:
        raise ValueError("database has no stories table")
    missing = sorted(set(STORY_COLUMNS) - columns)
    if missing:
        raise ValueError(f"stories table is missing columns: {', '.join(missing)}")

def publish(
    records: list[StoryRecord],
    db_path: Path,
    author: str,
    *,
    make_backup: bool,
) -> tuple[int, Path | None]:
    if not db_path.is_file():
        raise ValueError(f"database does not exist: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(db_path, timeout=5)
    except sqlite3.Error as exc:
        raise ValueError(f"cannot open database {db_path}: {exc}") from exc
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        check_schema(connection)
        staged: list[StagedCover] = []
        replaced: list[StagedCover] = []
        try:
            connection.execute("BEGIN IMMEDIATE")
            backup_path = backup_database(db_path) if make_backup else None
            for record in records:
                staged.append(stage_cover(record.cover_source, record.cover_target))
                if record.infographic_source is not None and record.infographic_target is not None:
                    staged.append(stage_cover(record.infographic_source, record.infographic_target))
            replaced = replace_staged(staged)
            for record in records:
                owner = connection.execute(
                    "SELECT user_id FROM stories WHERE id = ? LIMIT 1",
                    (record.story_id,),
                ).fetchone()
                if owner is not None and owner[0] != EDITORIAL_USER_ID:
                    raise ValueError(f"story ID is already owned by another user: {record.story_id}")
            for record in records:
                collision = connection.execute(
                    """SELECT id FROM stories
                       WHERE id <> ? AND (cover_url = ? OR instr(pages_json, ?) > 0)
                       LIMIT 1""",
                    (record.story_id, record.cover_url, record.cover_url),
                ).fetchone()
                if collision is not None:
                    raise ValueError(
                        f"cover URL already belongs to story {collision[0]}: {record.cover_url}"
                    )
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f000+00:00")
            rows = [story_row(record, author, now) for record in records]
            connection.executemany(SQLITE_UPSERT, rows)
            connection.commit()
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.rollback()
            if replaced:
                restore_covers(replaced)
            raise ValueError(f"database write failed: {exc}") from exc
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            if replaced:
                restore_covers(replaced)
            raise
        finally:
            for cover in staged:
                cover.temporary.unlink(missing_ok=True)
    except sqlite3.Error as exc:
        raise ValueError(f"database write failed: {exc}") from exc
    finally:
        connection.close()
    return sum(len(record.pages) for record in records), backup_path


UPSERT_SQL = """INSERT INTO stories
   (id, user_id, author_name, title, prompt, cover_url, text_model, image_model,
    public, pages_json, word_count, reading_minutes, created_at, updated_at)
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
   ON CONFLICT(id) DO UPDATE SET
     user_id=excluded.user_id,
     author_name=excluded.author_name,
     title=excluded.title,
     prompt=excluded.prompt,
     cover_url=excluded.cover_url,
     text_model=excluded.text_model,
     image_model=excluded.image_model,
     public=excluded.public,
     pages_json=excluded.pages_json,
     word_count=excluded.word_count,
     reading_minutes=excluded.reading_minutes,
     updated_at=excluded.updated_at"""

PG_UPSERT_SQL = UPSERT_SQL.replace("?", "%s")


def story_row(record: StoryRecord, author: str, now) -> tuple:
    """One row of the stories table, shared by both backends."""
    return (
        record.story_id,
        EDITORIAL_USER_ID,
        author,
        record.title,
        record.prompt,
        record.cover_url,
        "original",
        "qwen-image-2.1",
        1,
        json.dumps(record.pages, ensure_ascii=False, separators=(",", ":")),
        record.word_count,
        record.reading_minutes,
        now,
        now,
    )


def postgres_url(explicit: str) -> str:
    """The live database is Postgres; --database-url, then the env, then .env."""
    if explicit.strip():
        return explicit.strip()
    value = os.environ.get("DATABASE_URL", "").strip()
    if value:
        return value
    env = ROOT / ".env"
    if not env.is_file():
        return ""
    for line in env.read_text(encoding="utf-8").splitlines():
        key, separator, raw = line.partition("=")
        if separator and key.strip() == "DATABASE_URL":
            return raw.strip().strip("'\"")
    return ""


def publish_postgres(records: list[StoryRecord], dsn: str, author: str) -> int:
    """Upsert into Postgres. The Go app reads Postgres; SQLite is the legacy file.

    The column list, the ownership check and the cover-URL collision check are the
    same as the SQLite path, because they are what stops a batch from overwriting
    somebody else's story.
    """
    try:
        import psycopg2
    except ImportError as exc:
        raise ValueError(f"psycopg2 is required to publish to postgres: {exc}") from exc
    connection = psycopg2.connect(dsn)
    staged: list[StagedCover] = []
    replaced: list[StagedCover] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='stories'"
            )
            columns = {str(row[0]) for row in cursor.fetchall()}
            if not columns:
                raise ValueError("database has no stories table")
            missing = sorted(set(STORY_COLUMNS) - columns)
            if missing:
                raise ValueError(f"stories table is missing columns: {', '.join(missing)}")
            for record in records:
                staged.append(stage_cover(record.cover_source, record.cover_target))
                if record.infographic_source is not None and record.infographic_target is not None:
                    staged.append(stage_cover(record.infographic_source, record.infographic_target))
            replaced = replace_staged(staged)
            for record in records:
                cursor.execute("SELECT user_id FROM stories WHERE id = %s", (record.story_id,))
                owner = cursor.fetchone()
                if owner is not None and owner[0] != EDITORIAL_USER_ID:
                    raise ValueError(f"story ID is already owned by another user: {record.story_id}")
                cursor.execute(
                    """SELECT id FROM stories
                       WHERE id <> %s AND (cover_url = %s OR position(%s in pages_json) > 0)
                       LIMIT 1""",
                    (record.story_id, record.cover_url, record.cover_url),
                )
                collision = cursor.fetchone()
                if collision is not None:
                    raise ValueError(
                        f"cover URL already belongs to story {collision[0]}: {record.cover_url}"
                    )
            now = datetime.now(timezone.utc)
            cursor.executemany(
                PG_UPSERT_SQL,
                [story_row(record, author, now) for record in records],
            )
        connection.commit()
    except Exception:
        connection.rollback()
        if replaced:
            restore_covers(replaced)
        raise
    finally:
        for cover in staged:
            cover.temporary.unlink(missing_ok=True)
        connection.close()
    return sum(len(record.pages) for record in records)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--db", type=Path, default=None,
                        help="publish to this SQLite file instead of Postgres")
    parser.add_argument("--database-url", default="",
                        help="publish to Postgres; defaults to DATABASE_URL from the env or .env")
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--author", default="Reading Time")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args(argv)
    try:
        author = args.author.strip()
        if not author:
            raise ValueError("author must not be empty")
        manifest = repo_path(args.manifest, "manifest", must_exist=True)
        db_path = repo_path(args.db or DEFAULT_DB, "database")
        static_root = repo_path(args.static_root, "static root")
        records = load_records(manifest, static_root)
        page_count = sum(len(record.pages) for record in records)
        # Postgres is the live database and readingtime.db the legacy SQLite file
        # the Go app imported it from, so a published batch goes to Postgres unless
        # --db names a SQLite file outright.
        dsn = "" if args.db is not None else postgres_url(args.database_url)
        target = "postgres" if dsn else str(db_path)
        if args.dry_run:
            print(f"would publish {len(records)} stories, {page_count} pages to {target}")
            return 0
        if dsn:
            # The running app reads Postgres, so that is where a published batch
            # has to land; readingtime.db is the legacy SQLite file it imported.
            published_pages = publish_postgres(records, dsn, author)
            print(f"published {len(records)} stories, {published_pages} pages to postgres")
            return 0
        published_pages, backup_path = publish(records, db_path, author, make_backup=args.backup)
        print(f"published {len(records)} stories, {published_pages} pages to {db_path}")
        if backup_path is not None:
            print(f"backup {backup_path}")
        return 0
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"publish_manuscripts: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
