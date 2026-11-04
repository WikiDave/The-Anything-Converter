"""De terminal-app testen zonder echte terminal (Textual pilot)."""
import asyncio

import pytest

textual = pytest.importorskip("textual")
from PIL import Image  # noqa: E402

import tui  # noqa: E402


def make_png(path):
    Image.new("RGB", (400, 300), (40, 200, 90)).save(path)
    return path


async def wait_for(pred, timeout=30.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if pred():
            return True
        await asyncio.sleep(0.1)
    return False


def test_convert_image_in_terminal(tmp_path):
    src = make_png(tmp_path / "foto.png")
    out = tmp_path / "uit"

    async def run():
        app = tui.Converter(str(src))
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            assert "foto.png" in str(app.query_one("#fileinfo").render())
            app.query_one("#format").value = "webp"
            app.query_one("#outdir").value = str(out)
            await pilot.press("ctrl+s")
            ok = await wait_for(lambda: (out / "foto.webp").exists())
            await pilot.pause()
            assert ok, "geen resultaat"
            text = str(app.query_one("#result").render())
            assert "STATUS: OK" in text and "NIEUW" in text
            app.save_screenshot(str(tmp_path / "tui.svg"))

    asyncio.run(run())
    assert Image.open(out / "foto.webp").size == (400, 300)


def test_target_size_error_shown(tmp_path):
    src = make_png(tmp_path / "foto.png")

    async def run():
        app = tui.Converter(str(src))
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.query_one("#m-target").value = True
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert "Vul een doelgrootte in" in str(app.query_one("#result").render())

    asyncio.run(run())


def test_narrow_terminal_uses_small_logo():
    async def run():
        app = tui.Converter()
        async with app.run_test(size=(60, 30)) as pilot:
            await pilot.pause()
            assert str(app.query_one("#logo").render()).strip() == "ANYTHING CONVERTER"

    asyncio.run(run())
