"""Terminal zonder volledig scherm: opdrachten, eenvoudige modus, social media en PDF-werkbank."""
import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TUI = [sys.executable, "-W", "ignore", str(ROOT / "tui.py")]


def run(*args, inp=None, cwd=None):
    return subprocess.run([*TUI, *args], input=inp, capture_output=True, text=True, cwd=cwd, timeout=120)


def test_convert_command_and_errors(tmp_path):
    Image.new("RGB", (300, 200), (10, 120, 200)).save(tmp_path / "a.png")
    r = run("converteer", "a.png", "--naar", "webp", cwd=tmp_path)
    assert r.returncode == 0 and (tmp_path / "a.webp").exists(), r.stdout + r.stderr
    r = run("converteer", "a.png", "--naar", "xyz", cwd=tmp_path)
    assert r.returncode == 1 and "cannot become .xyz" in r.stdout
    assert "terminal" in run("--version").stdout


def test_simple_mode_works_without_a_terminal(tmp_path):
    Image.new("RGB", (100, 100), "white").save(tmp_path / "b.png")
    # niet interactief (pijp): start vanzelf de eenvoudige modus
    r = run(inp="1\nb.png\n1\n2\n\n9\n", cwd=tmp_path)
    assert "simple mode" in r.stdout and "WHAT DO YOU WANT TO DO?" in r.stdout
    assert (tmp_path / "b_edited.png").exists() or (tmp_path / "b.png").exists()
    assert "OK:" in r.stdout, r.stdout[-800:]


def test_ascii_output(tmp_path, monkeypatch):
    Image.new("RGB", (100, 100), "white").save(tmp_path / "c.png")
    r = subprocess.run([*TUI, "--ascii", "converteer", "c.png", "--naar", "jpg"], capture_output=True, cwd=tmp_path,
                       timeout=120)
    r.stdout.decode("ascii")  # geen enkel teken buiten ASCII


def test_social_presets(tmp_path):
    from converter import social
    pano = tmp_path / "pano.jpg"
    Image.new("RGB", (6000, 1500), (90, 140, 200)).save(pano)
    out = social.image(pano, tmp_path, "ig-pano")
    names = zipfile.ZipFile(out).namelist()
    assert len(names) >= 3
    first = Image.open(io.BytesIO(zipfile.ZipFile(out).read(names[0])))
    assert first.size == (1080, 1350)
    story = social.image(pano, tmp_path, "ig-story", fit="contain")
    assert Image.open(story).size == (1080, 1920)


def test_social_video(tmp_path):
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10", "-t", "1",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    from converter import social
    from converter.util import ffprobe
    for fit in ("cover", "contain"):
        out = social.video(src, tmp_path, "tt-video", fit)
        v = next(s for s in ffprobe(out)["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (1080, 1920)
        out.unlink()


def test_pdf_workbench(tmp_path):
    fitz = pytest.importorskip("fitz")
    from converter import pdftools
    files = []
    for n in range(3):
        d = fitz.open()
        d.new_page().insert_text((72, 72), f"pagina {n + 1}")
        d.save(tmp_path / f"{n}.pdf")
        files.append(tmp_path / f"{n}.pdf")
    Image.new("RGB", (200, 300), "red").save(tmp_path / "foto.jpg")
    merged = pdftools.merge(files + [tmp_path / "foto.jpg"], tmp_path / "samen.pdf")
    assert len(fitz.open(merged)) == 4
    assert len(zipfile.ZipFile(pdftools.split(merged, tmp_path)).namelist()) == 4
    part = pdftools.split(merged, tmp_path, "2-3")
    assert len(fitz.open(part)) == 2
    edited = pdftools.edit_pages(merged, tmp_path / "e.pdf", delete="1", rotate="1-2", angle=90)
    doc = fitz.open(edited)
    assert len(doc) == 3 and doc[0].rotation == 90
    with pytest.raises(Exception):
        pdftools.parse_pages("9", 4)


def test_tui_tabs_and_tools():
    import asyncio
    import tui

    async def go():
        app = tui.build_app(False)()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.query_one("#tabs").active = "tab-tools"
            await pilot.pause()
            await pilot.click("#tool-0")  # PDF naar Word
            await pilot.pause()
            assert app.query_one("#tabs").active == "tab-convert" and app.preset == "docx"
            await pilot.press("f1")
            await pilot.pause()
            assert type(app.screen).__name__ == "HelpScreen"

    asyncio.run(go())


def test_tui_ascii_mode_has_no_unicode_logo():
    import asyncio
    import tui

    async def go():
        app = tui.build_app(True)()
        async with app.run_test(size=(100, 45)) as pilot:
            await pilot.pause()
            logo = str(app.query_one("#logo").render())
            assert logo.isascii()

    asyncio.run(go())
