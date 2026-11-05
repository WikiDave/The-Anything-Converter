"""Catalogus en herkenning: elke familie minstens één echte omzetting, dubbelzinnige extensies, half gedownloade bestanden."""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from formats_report import make_sample  # noqa: E402

from converter.catalog import catalog, describe  # noqa: E402
from converter.detect import analyse_path, targets_for  # noqa: E402
from converter.jobs import run_conversion  # noqa: E402

CASES = [  # (extensie, verwachte soort, uitvoer om te testen)
    ("nfo", "text", "png"), ("py", "text", "html"), ("md", "text", "docx"), ("json", "data", "yaml"),
    ("yaml", "data", "xml"), ("toml", "data", "json"), ("csv", "spreadsheet", "json"), ("sqlite", "data", "xlsx"),
    ("dbf", "data", "csv"), ("ipynb", "data", "md"), ("ofx", "data", "csv"), ("sta", "data", "xlsx"),
    ("srt", "subtitle", "ass"), ("ass", "subtitle", "srt"), ("lrc", "subtitle", "srt"), ("m3u", "playlist", "xspf"),
    ("mid", "midi", "txt"), ("woff2", "font", "ttf"), ("ttf", "font", "png"), ("eml", "mail", "zip"),
    ("mbox", "mail", "csv"), ("vcf", "contact", "csv"), ("ics", "calendar", "xlsx"), ("gpx", "gps", "kml"),
    ("igc", "gps", "gpx"), ("stl", "model3d", "obj"), ("dxf", "cad", "svg"), ("svg", "vector", "pdf"),
    ("ai", "vector", "png"), ("pem", "cert", "txt"), ("key", "cert", "der"), ("dcm", "medical", "png"),
    ("gz", "compressed", "uitpakken"), ("deb", "archive2", "txt"), ("cbz", "comic", "pdf"), ("gguf", "info", "txt"),
    ("torrent", "info", "txt"), ("heic", "image", "jpg"), ("wv", "audio", "mp3"), ("mxf", "video", "mp4"),
    ("mhtml", "text", "txt"),
]


def test_catalog_has_the_list():
    cat = catalog()
    assert len(cat) > 1000
    assert "Canon" in describe(Path("foto.cr2"))
    assert cat["kdbx"][0][1].startswith("KeePass")


@pytest.mark.parametrize("ext,cat,fmt", CASES)
def test_family_conversion(tmp_path, ext, cat, fmt):
    src = make_sample(ext, tmp_path)
    if src is None:
        pytest.skip("geen voorbeeld te maken op deze machine")
    got, eff, targets = targets_for(src)
    assert got == cat, (ext, got)
    assert fmt in targets
    out = tmp_path / "uit"
    out.mkdir()
    res = run_conversion(src, out, got, {"format": fmt})
    assert res.exists() and res.stat().st_size > 0


def test_partial_download_is_recognised(tmp_path):
    src = make_sample("png", tmp_path)
    part = tmp_path / "vakantie.png.crdownload"
    shutil.copy(src, part)
    cat, eff = analyse_path(part)
    assert (cat, eff) == ("image", "png")
    out = tmp_path / "uit"
    out.mkdir()
    assert run_conversion(part, out, cat, {"format": "jpg"}).suffix == ".jpg"


def test_ambiguous_extensions(tmp_path):
    ts = tmp_path / "code.ts"
    ts.write_text("export const a: number = 1;\n")
    assert analyse_path(ts)[0] == "text"
    video = make_sample("ts", tmp_path)
    if video:
        assert analyse_path(video)[0] == "video"
    pub = tmp_path / "id.pub"
    pub.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl test")
    assert analyse_path(pub)[0] == "cert"
    md = tmp_path / "leesmij.md"
    md.write_text("# Titel\n")
    assert analyse_path(md)[0] == "text"


def test_pickles_are_never_opened(tmp_path):
    p = tmp_path / "model.pkl"
    p.write_bytes(b"\x80\x04\x95\x00")
    cat, eff, targets = targets_for(p)
    assert cat == "info" and targets == ["txt", "zip", "7z"]
    out = tmp_path / "uit"
    out.mkdir()
    report = run_conversion(p, out, cat, {"format": "txt"}).read_text()
    assert "not opened" in report
