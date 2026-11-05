"""Viruscontrole testen met een nagebootste ClamAV (geen echte scanner nodig)."""
import os
import stat
import sys

import pytest

from converter import settings, virus

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="nep-scanner is een shellscript")

FAKE_CLAMSCAN = """#!/bin/sh
# Nep-ClamAV: alles met EICAR erin is "besmet".
for a in "$@"; do f="$a"; done
if grep -rq "EICAR-STANDARD-ANTIVIRUS-TEST-FILE" "$f" 2>/dev/null; then
  echo "$f: Eicar-Test-Signature FOUND"; exit 1
fi
exit 0
"""
EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@pytest.fixture
def fake_clam(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "clamscan"
    exe.write_text(FAKE_CLAMSCAN)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}/usr/bin:/bin")
    return exe


def test_clean_file(tmp_path, fake_clam):
    f = tmp_path / "goed.txt"
    f.write_text("hallo")
    r = virus.check(f)
    assert r["status"] == "clean" and r["local"]["engine"] == "ClamAV"
    assert r["files"][0]["virustotal"].endswith(r["files"][0]["sha256"])


def test_infected_file(tmp_path, fake_clam):
    f = tmp_path / "eicar.com"
    f.write_text(EICAR)
    r = virus.check(f)
    assert r["status"] == "infected" and "Eicar" in r["local"]["detail"]


def test_infected_in_folder(tmp_path, fake_clam):
    d = tmp_path / "torrent" / "map"
    d.mkdir(parents=True)
    (d / "ok.txt").write_text("ok")
    (d / "slecht.exe").write_text(EICAR)
    r = virus.check(tmp_path / "torrent")
    assert r["status"] == "infected" and len(r["files"]) == 2


def test_no_scanner(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    f = tmp_path / "x.bin"
    f.write_bytes(b"123")
    r = virus.check(f)
    assert r["status"] == "unknown" and "no virus scanner" in r["local"]["detail"]
    assert len(r["files"][0]["sha256"]) == 64


def test_settings_and_api(tmp_path, monkeypatch, fake_clam):
    monkeypatch.setenv("CONVERTER_SETTINGS", str(tmp_path / "s.json"))
    import app as appmod
    c = appmod.app.test_client()
    assert c.get("/api/settings").get_json()["vt_key_set"] is False
    assert c.post("/api/settings", json={"vt_key": "te-kort"}).status_code == 400
    assert c.post("/api/settings", json={"vt_key": "a" * 64}).get_json()["vt_key_set"] is True
    assert settings.load()["vt_key"] == "a" * 64
    # geopend bestand op verzoek scannen
    f = tmp_path / "eicar.txt"
    f.write_text(EICAR)
    up = appmod.register_upload("u1", f)
    monkeypatch.setattr(virus, "virustotal", lambda d, k: None)  # geen netwerk in tests
    assert c.post(f"/api/scan/{up['id']}").get_json()["status"] == "infected"


def test_infected_download_is_not_opened(tmp_path):
    import app as appmod
    from converter.jobs import Job
    f = tmp_path / "dl" / "video.mp4"
    f.parent.mkdir()
    f.write_bytes(b"0" * 10)
    job = Job(id="v1", src=f.parent, category="fetch", opts={}, kind="fetch", status="done", result=f)
    job.extra.update(uid="vv", virus={"status": "infected", "local": {"engine": "ClamAV", "status": "infected", "detail": "x"}, "files": []})
    appmod.jobs.jobs["v1"] = job
    c = appmod.app.test_client()
    st = c.get("/api/job/v1").get_json()
    assert "upload" not in st and st["virus"]["status"] == "infected"
