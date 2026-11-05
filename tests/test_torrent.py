"""Torrent-download testen zonder internet: een tweede libtorrent-sessie deelt de bestanden."""
import os
import time

import pytest

lt = pytest.importorskip("libtorrent")

from converter.torrent import download  # noqa: E402
from converter.util import ConversionError  # noqa: E402


def make_seed(tmp_path):
    src = tmp_path / "seed" / "pakket"
    (src / "map").mkdir(parents=True)
    (src / "a.bin").write_bytes(os.urandom(300_000))
    (src / "map" / "b.txt").write_text("hallo torrent\n" * 1000)
    fs = lt.file_storage()
    lt.add_files(fs, str(src))
    ct = lt.create_torrent(fs, 16384)
    lt.set_piece_hashes(ct, str(src.parent))
    data = lt.bencode(ct.generate())
    ses = lt.session({"listen_interfaces": "127.0.0.1:0", "enable_dht": False, "enable_lsd": False,
                      "enable_upnp": False, "enable_natpmp": False})
    p = lt.add_torrent_params()
    p.ti = lt.torrent_info(lt.bdecode(data))
    p.save_path = str(src.parent)
    h = ses.add_torrent(p)
    for _ in range(100):
        if h.status().is_seeding:
            break
        time.sleep(0.1)
    return ses, data, ses.listen_port()


def test_download_from_local_seed(tmp_path):
    ses, data, port = make_seed(tmp_path)
    seen = []
    res = download(data, tmp_path / "out", progress=lambda f, m: seen.append(m), peers=[("127.0.0.1", port)])
    paths = sorted(f["path"].replace("\\", "/") for f in res["files"])
    assert paths == ["pakket/a.bin", "pakket/map/b.txt"]
    got = (tmp_path / "out" / "pakket" / "a.bin").read_bytes()
    assert got == (tmp_path / "seed" / "pakket" / "a.bin").read_bytes()
    assert any(m.startswith("Downloading") for m in seen)
    del ses


def test_rejects_bad_input(tmp_path):
    with pytest.raises(ConversionError):
        download("https://example.com/niet-magnet", tmp_path)
    with pytest.raises(ConversionError):
        download(b"dit is geen torrent", tmp_path)


def test_cancel(tmp_path):
    with pytest.raises(ConversionError, match="Gestopt"):
        download("magnet:?xt=urn:btih:" + "a" * 40, tmp_path, cancelled=lambda: True)


def test_torrent_endpoints(tmp_path, monkeypatch):
    """Bestanden van een afgeronde torrent: opslaan, openen in de converter, en geen paden buiten de map."""
    import app as appmod
    from converter.jobs import Job

    root = tmp_path / "dl"
    (root / "pakket").mkdir(parents=True)
    (root / "pakket" / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    (tmp_path / "geheim.txt").write_text("niet delen")
    job = Job(id="t1", src=root, category="torrent", opts={}, kind="torrent", status="done", result=root)
    job.extra.update(name="pakket", files=[{"idx": 0, "path": "pakket/foto.png", "size": 108},
                                           {"idx": 1, "path": "../geheim.txt", "size": 10}])
    appmod.jobs.jobs["t1"] = job
    c = appmod.app.test_client()
    st = c.get("/api/job/t1").get_json()
    assert st["name"] == "pakket" and len(st["files"]) == 2
    r = c.get("/api/torrent/t1/file/0")
    assert r.status_code == 200 and r.data.startswith(b"\x89PNG")
    assert c.get("/api/torrent/t1/file/1").status_code == 404  # buiten de downloadmap
    assert c.get("/api/torrent/t1/file/9").status_code == 404
    up = c.post("/api/torrent/t1/open/0").get_json()
    assert up["name"] == "foto.png" and up["id"]
    assert c.post("/api/torrent", json={"magnet": "https://geen-magnet"}).status_code == 400
