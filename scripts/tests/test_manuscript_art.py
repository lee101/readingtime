import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_manuscript_covers as covers  # noqa: E402
import generate_manuscript_page_art as art  # noqa: E402

ROOT = art.ROOT
KEY = "manuscripts/accessible/07-the-lantern-at-the-end-of-the-ridge.md"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_pick_model_prefers_qwen_image():
    assert covers.pick_model(["flux-schnell", "qwen-image-edit", "qwen-image"]) == "qwen-image"
    assert covers.pick_model(["flux", "qwen-image-2.1"]) == "qwen-image-2.1"
    assert covers.pick_model(["flux"]) is None


def test_discover_model(monkeypatch):
    body = json.dumps({"data": [{"id": "sdxl-turbo"}, {"id": "qwen-image"}]}).encode()
    seen = []

    def fake(url, timeout=0):
        seen.append(url)
        return FakeResponse(body)

    monkeypatch.setattr(covers.urllib.request, "urlopen", fake)
    monkeypatch.delenv("OMNISERVE_NATIVE_IMAGE_MODEL", raising=False)
    assert covers.discover_model("http://x:1/") == "qwen-image"
    assert seen == ["http://x:1/v1/models"]
    monkeypatch.setenv("OMNISERVE_NATIVE_IMAGE_MODEL", "custom")
    assert covers.discover_model("http://x:1") == "custom"


def test_discover_model_none(monkeypatch):
    monkeypatch.delenv("OMNISERVE_NATIVE_IMAGE_MODEL", raising=False)
    monkeypatch.setattr(
        covers.urllib.request, "urlopen",
        lambda url, timeout=0: FakeResponse(json.dumps({"data": [{"id": "flux"}]}).encode()),
    )
    with pytest.raises(RuntimeError, match="no qwen image model"):
        covers.discover_model("http://x")


def test_parse_pages():
    assert art.parse_pages("4,8", 11) == {4, 8}
    assert art.parse_pages("3-5", 11) == {3, 4, 5}
    for bad in ("0", "11", "x", ""):
        with pytest.raises(ValueError):
            art.parse_pages(bad, 11)


def test_check_world(tmp_path):
    (tmp_path / "real.md").write_text("x")
    art.check_world("real", tmp_path)
    with pytest.raises(ValueError, match="unknown world 'nope'"):
        art.check_world("nope", tmp_path)


def test_single_child_clause():
    assert art.names_single_child("seven-year-old Sella, the girl in yellow, walks")
    assert not art.names_single_child("two children walk with a seven-year-old girl")
    assert not art.names_single_child("an old woman on a cliff")


def test_prompt_strips_and_adds_clause():
    base = art.compose_prompt("A scene. " + art.NO_TEXT_CLAUSE, "style.", "accessible", 2, 5)
    assert base.count(art.NO_TEXT_CLAUSE) == 1


def test_request_page_parses_b64(monkeypatch):
    import base64

    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "WEBP")
    body = json.dumps({"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}).encode()

    class R(FakeResponse):
        headers = type("H", (), {"get_content_type": lambda self: "application/json"})()

    monkeypatch.setattr(art.urllib.request, "urlopen", lambda req, timeout=0: R(body))
    assert art.request_page("http://x", "m", "p", 1, (8, 8), "", 5) == buf.getvalue()


def test_list_pages_real_story(capsys):
    rc = art.main(["--list-pages", "--only", "07-the-lantern", "--manifest",
                   str(ROOT / "manuscripts/lantern-coast-covers.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "pages=10 prompts=10 OK" in out
    assert "solo" in out


def test_only_pages_and_no_db_generate(tmp_path, monkeypatch, capsys):
    calls = []
    buf = io.BytesIO()
    Image.new("RGB", (768, 768), (200, 10, 10)).save(buf, "WEBP")

    monkeypatch.setattr(covers, "discover_model", lambda base, model=None: "qwen-image")

    def fake(base, model, prompt, seed, size, secret, timeout):
        calls.append(prompt)
        return buf.getvalue()

    monkeypatch.setattr(art, "request_page", fake)
    rc = art.main([
        "--no-db", "--only", "07-the-lantern", "--only-pages", "4,8",
        "--manifest", str(ROOT / "manuscripts/lantern-coast-covers.json"),
        "--output", str(tmp_path),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert len(calls) == 2
    assert "p04" in out and "p08" in out and "s/image" in out
    files = sorted(p.name for p in tmp_path.rglob("*.webp"))
    assert files == ["04.webp", "08.webp"]
    assert any("exactly one child" in c for c in calls)

    rc = art.main(["--contact-sheet", str(tmp_path / "sheets"), "--only", "07-the-lantern",
                   "--manifest", str(ROOT / "manuscripts/lantern-coast-covers.json"),
                   "--output", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "sheets" / "07-the-lantern-at-the-end-of-the-ridge.jpg").exists()


def test_bad_world_errors(tmp_path, capsys):
    frag = tmp_path / "f"
    frag.mkdir()
    src = json.loads((ROOT / "manuscripts/page-prompts/07-the-lantern-at-the-end-of-the-ridge.json").read_text())
    src["world"] = "no-such-world"
    (frag / "a.json").write_text(json.dumps(src))
    rc = art.main(["--list-pages", "--only", "07-the-lantern", "--fragments", str(frag),
                   "--manifest", str(ROOT / "manuscripts/lantern-coast-covers.json")])
    assert rc == 1
    assert "BAD WORLD" in capsys.readouterr().out
