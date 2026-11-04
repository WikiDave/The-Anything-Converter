"""Test het ophalen via een link met een lokale webserver (geen internet nodig)."""
import functools
import http.server
import shutil
import subprocess
import threading

import pytest

pytest.importorskip("yt_dlp")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg ontbreekt")

from converter.fetch import download  # noqa: E402
from converter.util import ConversionError  # noqa: E402


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("www")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
                    "-f", "lavfi", "-i", "sine", "-t", "3", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(root / "clip.mp4")], check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_download_direct_link(server, tmp_path):
    seen = []
    out = download(server + "/clip.mp4", tmp_path, progress=lambda f, m: seen.append(f))
    assert out.exists() and out.stat().st_size > 1000
    assert seen and max(seen) <= 1


def test_rejects_non_http(tmp_path):
    with pytest.raises(ConversionError):
        download("file:///etc/passwd", tmp_path)
    with pytest.raises(ConversionError):
        download("geen link", tmp_path)


def test_missing_file_gives_dutch_error(server, tmp_path):
    with pytest.raises(ConversionError) as e:
        download(server + "/bestaat-niet.mp4", tmp_path)
    assert "mislukt" in str(e.value).lower() or "niet" in str(e.value).lower()
