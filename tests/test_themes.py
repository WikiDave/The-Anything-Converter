from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_browser_version_has_the_same_colour_picker():
    js = (ROOT / "static" / "themes.js").read_text(encoding="utf-8")
    assert js in (ROOT / "index.html").read_text(encoding="utf-8"), "run: copy static/themes.js into index.html"
