from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "manuscripts" / "covers.json"
DEFAULT_OUTPUT = ROOT / "manuscripts" / "art"
DEFAULT_SIZE = (1024, 1536)
DEFAULT_BASE = "http://127.0.0.1:8790"


def pick_model(ids: list[str]) -> str | None:
    if "qwen-image" in ids:
        return "qwen-image"
    for name in ids:
        if "qwen" in name.lower() and "image" in name.lower() and "edit" not in name.lower():
            return name
    return None


def discover_model(base: str, explicit: str | None = None, timeout: int = 10) -> str:
    """Env/flag override, else the qwen image model listed by GET /v1/models."""
    chosen = explicit or os.environ.get("OMNISERVE_NATIVE_IMAGE_MODEL", "").strip()
    if chosen:
        return chosen
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}/v1/models", timeout=timeout) as response:
            document = json.loads(response.read())
    except (OSError, ValueError) as error:
        raise RuntimeError(f"cannot list models at {base}/v1/models: {error}") from error
    ids = [str(entry.get("id", "")) for entry in document.get("data", [])]
    found = pick_model(ids)
    if found is None:
        raise RuntimeError(f"no qwen image model at {base}; models: {', '.join(ids)}")
    return found


def parse_size(raw: str) -> tuple[int, int]:
    width, separator, height = raw.partition("x")
    if not separator or not width.isdigit() or not height.isdigit():
        raise argparse.ArgumentTypeError("size must look like 1024x1536")
    return int(width), int(height)


def read_secret(env_name: str, secret_file: Path | None) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    if secret_file is None or not secret_file.exists():
        return ""
    try:
        contents = secret_file.read_text()
    except PermissionError:
        contents = subprocess.run(
            ["sudo", "-n", "cat", str(secret_file)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    for raw in contents.splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == env_name:
            return value.strip().strip("'\"")
    return ""


def request_cover(base: str, model: str, prompt: str, seed: int, size: tuple[int, int], secret: str, timeout: int) -> tuple[bytes, int]:
    payload = {
        "model": model,
        "prompt": prompt,
        "width": size[0],
        "height": size[1],
        "steps": 20,
        "seed": seed,
        "output_format": "webp",
        "n": 1,
    }
    headers = {
        "Accept": "application/json, image/*",
        "Content-Type": "application/json",
        "X-Omniserve-Tier": "free",
    }
    if secret:
        headers["X-API-Key"] = secret
    request = urllib.request.Request(
        f"{base.rstrip('/')}/v1/images/generations",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        detail = error.read(4096).decode("utf-8", "replace").strip()
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    if content_type == "image":
        return body, 0
    document = json.loads(body)
    entries = document.get("data", [])
    if not entries or not entries[0].get("b64_json"):
        raise RuntimeError("Qwen returned no image")
    elapsed = entries[0].get("inference_time_ms", 0)
    return base64.b64decode(entries[0]["b64_json"], validate=True), int(elapsed or 0)


def normalize_cover(raw: bytes, size: tuple[int, int]) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        if image.size != size:
            raise RuntimeError(f"Qwen returned {image.size}, expected {size}")
        if image.format == "WEBP":
            return raw
        output = io.BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=90, method=6)
        return output.getvalue()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def ensure_cover_link(source: Path, target: Path, title: str) -> bool:
    text = source.read_text(encoding="utf-8")
    if any(line.startswith("![Cover art:") for line in text.splitlines()):
        return False
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise RuntimeError("manuscript must start with an H1")
    body = lines[1:]
    while body and not body[0].strip():
        body.pop(0)
    relative = Path(os.path.relpath(target, source.parent)).as_posix()
    link = f"![Cover art: {title}]({relative})"
    atomic_write(source, ("\n".join([lines[0], "", link, "", *body]) + "\n").encode())
    return True


def selected(item: dict[str, object], selectors: list[str]) -> bool:
    if not selectors:
        return True
    source = str(item["path"]).casefold()
    return any(selector.casefold() in source for selector in selectors)


# One entry per medium, keyed by level. `painterly` is the house default and the
# one every existing manifest was generated with; `anime` and `comic` are second
# registers for batches whose art direction asks for them, selected with
# `--style`.
MEDIUM_BY_STYLE = {
    "painterly": {
        "accessible": "warm painterly children's book illustration, luminous color, gentle wonder, photographic lighting, painterly and not flat cartoon",
        "intermediate": "painterly fantasy adventure illustration, expressive textures, clear silhouettes, rich environmental detail",
        "advanced": "sophisticated painterly fantasy illustration, cinematic composition, tactile detail, restrained dramatic light",
    },
    "anime": {
        "accessible": "modern Japanese anime key visual for a children's book, clean confident linework, flat cel shading, soft hand-painted background, expressive round face, luminous color",
        "intermediate": "cinematic anime film key visual, precise linework, even cel shading, hand-painted background art, expressive close-up, rich environmental detail",
        "advanced": "moody anime film still, fine confident linework, cinematic cel shading, hand-painted dusk and night backgrounds, restrained dramatic light",
    },
    "comic": {
        "accessible": "bold inked illustration, thick black outlines, flat blocks of saturated colour, halftone dot shading in the shadows, bright poster palette, expressive cartoon face with real hands",
        "intermediate": "bold inked illustration, thick black outlines, flat blocks of colour, hard shadow shapes, halftone dot shading, dramatic foreshortening, rich environmental detail",
        "advanced": "adult inked illustration, heavy black outlines, moody blocks of flat colour, screentone shading, noir lighting, cinematic composition, restrained and grounded",
    },
}


def art_direction(item: dict[str, object], style_preset: str = "painterly") -> str:
    level = str(item["level"])
    audience = str(item["audience"])
    normalized = audience.casefold().replace("ages", "").replace("age", "").strip()
    style = MEDIUM_BY_STYLE[style_preset][level]
    if normalized.startswith(("5–", "5-", "6–", "6-", "7–", "7-", "8–", "8-")):
        framing = "character-forward, safe and inviting, with no horror"
    elif normalized.startswith(("9–", "9-", "10–", "10-", "11–", "11-", "12–", "12-", "13–", "13-", "14–", "14-")):
        framing = "youthful protagonists and an emotionally clear heroic moment"
    else:
        framing = "adult protagonists, nuanced body language, grounded and non-glorifying"
    return f"{style}; {framing}; vertical full-bleed cover composition with no frame or margin; absolutely no text, no letters, no characters, no writing, no numbers, no glyphs, no signage, no watermark, no captions, no title, no border; every surface is plain and blank"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base", default=os.environ.get("OMNISERVE_NATIVE_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--model", default=None, help="default: env, else autodiscover")
    parser.add_argument("--secret-env", default="OMNISERVE_NATIVE_SECRET")
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--size", type=parse_size, default=DEFAULT_SIZE)
    parser.add_argument("--style", choices=sorted(MEDIUM_BY_STYLE), default="painterly",
                        help="medium register appended to each cover prompt")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed-salt", type=int, default=0,
                        help="re-roll the deterministic seed; use to replace a cover that came back broken")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    document = json.loads(args.manifest.read_text())
    covers = document["covers"]
    secret = read_secret(args.secret_env, args.secret_file)
    linked = 0
    failures = 0
    generated = 0
    started = time.time()
    model = args.model

    for item in covers:
        if not selected(item, args.only):
            continue
        source = ROOT / str(item["path"])
        level = str(item["level"])
        target = args.output / level / f"{source.stem}.webp"
        if target.exists() and not args.force:
            if ensure_cover_link(source, target, str(item["title"])):
                linked += 1
            print(f"skip {source.relative_to(ROOT)}")
        prompt = f"{item['prompt']}. {art_direction(item, args.style)}"
        if args.dry_run:
            print(f"plan {source.relative_to(ROOT)} -> {target.relative_to(ROOT)} {args.size[0]}x{args.size[1]}")
            continue
        # A handful of seeds degenerate into a landscape with no subject on this
        # model whatever the prompt says, so a broken cover cannot be re-rolled by
        # rewriting its prompt alone; --seed-salt is how it is re-rolled. Mirrors
        # generate_manuscript_page_art.py's flag of the same name.
        material = str(item["path"]) if not args.seed_salt else f"{item['path']}#{args.seed_salt}"
        seed = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big") % (2**63 - 1)
        try:
            model = model or discover_model(args.base)
            t0 = time.time()
            raw, elapsed = request_cover(args.base, model, prompt, seed, args.size, secret, args.timeout)
            elapsed = elapsed or int((time.time() - t0) * 1000)
            atomic_write(target, normalize_cover(raw, args.size))
            if ensure_cover_link(source, target, str(item["title"])):
                linked += 1
            generated += 1
            print(f"made {source.relative_to(ROOT)} {target.stat().st_size} bytes {elapsed} ms")
        except Exception as error:
            failures += 1
            print(f"failed {source.relative_to(ROOT)}: {error}", file=sys.stderr)

    wall = time.time() - started
    rate = generated / wall * 60 if wall and generated else 0.0
    print(f"generated {generated}, linked {linked}, failed {failures}, {wall:.0f}s, {rate:.2f}/min")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
