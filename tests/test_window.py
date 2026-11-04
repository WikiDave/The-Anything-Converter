"""Programmavenster: opslaan via de lokale server en de terminalknop (zonder echt venster)."""
import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
window = pytest.importorskip("window")

import app as server  # noqa: E402


@pytest.fixture
def live(tmp_path):
    from werkzeug.serving import make_server
    import threading
    srv = make_server("127.0.0.1", 0, server.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/"
    srv.shutdown()


def test_save_url_uses_server_filename(live, tmp_path, monkeypatch):
    up = server.app.test_client().post("/api/upload", data={"file": (__import__("io").BytesIO(b"hallo"), "a b.txt")})
    uid = up.get_json()["id"]
    api = window.Api(live)
    asked = {}
    monkeypatch.setattr(api, "_ask", lambda name: asked.setdefault("name", name) and str(tmp_path / "uit.txt"))
    res = api.save_url(f"/api/file/{uid}?download=1")
    assert res == {"path": str(tmp_path / "uit.txt")}
    assert asked["name"].endswith(".txt")
    assert (tmp_path / "uit.txt").read_bytes() == b"hallo"


def test_save_cancelled_and_bad_path(live, monkeypatch):
    api = window.Api(live)
    monkeypatch.setattr(api, "_ask", lambda name: None)
    assert api.save_url("https://example.com/x")["error"]
    assert api.save_begin("x.pdf") == {"cancelled": True}


def test_save_in_chunks(live, tmp_path, monkeypatch):
    api = window.Api(live)
    monkeypatch.setattr(api, "_ask", lambda name: str(tmp_path / name))
    assert api.save_begin("doc.pdf")["path"].endswith("doc.pdf")
    data = bytes(range(256)) * 5000
    for i in range(0, len(data), 3 * 1024):
        assert api.save_chunk(base64.b64encode(data[i:i + 3 * 1024]).decode())
    assert api.save_end()["path"].endswith("doc.pdf")
    assert (tmp_path / "doc.pdf").read_bytes() == data


def test_external_links_only_web():
    api = window.Api("http://127.0.0.1:1/")
    assert api.open_external("file:///etc/passwd") is False
    assert api.open_external("javascript:alert(1)") is False


def test_terminal_command_points_to_tui():
    from converter.terminal import tui_command
    cmd = tui_command()
    assert cmd[-1].endswith("tui.py") and Path(cmd[-1]).exists()


def test_ping_reports_window():
    server.app.config["WINDOW"] = "native"
    try:
        assert server.app.test_client().get("/api/ping").get_json()["window"] == "native"
    finally:
        server.app.config.pop("WINDOW")
