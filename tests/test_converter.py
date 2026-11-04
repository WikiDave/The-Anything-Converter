"""Integratietests: draaien echte conversies (vereist ffmpeg; sommige tests LibreOffice/pandoc)."""
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from converter.jobs import run_conversion
from converter.util import ConversionError, ffprobe, parse_size, parse_time

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg ontbreekt")
needs_lo = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice ontbreekt")
MB = 1024 * 1024


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    p = tmp_path_factory.mktemp("src") / "clip.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=frequency=440",
       "-t", "12", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-shortest", str(p))
    return p


@pytest.fixture(scope="module")
def photo(tmp_path_factory):
    p = tmp_path_factory.mktemp("src") / "foto.png"
    ff("-f", "lavfi", "-i", "testsrc2=size=1600x1000", "-frames:v", "1", str(p))
    return p


def duration(p):
    return float(ffprobe(p)["format"]["duration"])


def test_parse_helpers():
    assert parse_size("800 KB") == 800 * 1024
    assert parse_size(2.5, "MB") == int(2.5 * MB)
    assert parse_time("1:23.5") == 83.5
    assert parse_time("") is None
    with pytest.raises(ConversionError):
        parse_size("abc")


@needs_ffmpeg
def test_video_trim_and_convert(video, tmp_path):
    out = run_conversion(video, tmp_path, "video", {"format": "webm", "trim_start": "2", "trim_end": "5"})
    assert out.suffix == ".webm"
    assert abs(duration(out) - 3) < 0.3


@needs_ffmpeg
def test_video_fast_trim(video, tmp_path):
    out = run_conversion(video, tmp_path, "video", {"format": "mp4", "trim_start": "0", "trim_end": "4", "fast_trim": True})
    assert duration(out) < 6


@needs_ffmpeg
def test_video_target_smaller(video, tmp_path):
    target = int(0.5 * MB)
    out = run_conversion(video, tmp_path, "video", {"format": "mp4", "target_bytes": target})
    assert out.stat().st_size <= target * 1.05


@needs_ffmpeg
def test_video_target_bigger(video, tmp_path):
    target = video.stat().st_size * 2
    out = run_conversion(video, tmp_path, "video", {"format": "mp4", "target_bytes": target})
    assert out.stat().st_size > video.stat().st_size * 1.5


@needs_ffmpeg
def test_video_to_mp3_target(video, tmp_path):
    out = run_conversion(video, tmp_path, "video", {"format": "mp3", "target_bytes": 100 * 1024})
    assert out.suffix == ".mp3" and out.stat().st_size <= 105 * 1024


@needs_ffmpeg
def test_video_to_gif_target(video, tmp_path):
    out = run_conversion(video, tmp_path, "video", {"format": "gif", "trim_end": "3", "target_bytes": 1 * MB})
    assert out.stat().st_size <= MB


@needs_ffmpeg
def test_target_too_small_errors(video, tmp_path):
    with pytest.raises(ConversionError):
        run_conversion(video, tmp_path, "video", {"format": "mp4", "target_bytes": 10 * 1024})


@pytest.mark.parametrize("fmt", ["jpg", "webp", "png"])
def test_image_target_smaller(photo, tmp_path, fmt):
    target = 60 * 1024
    out = run_conversion(photo, tmp_path, "image", {"format": fmt, "target_bytes": target})
    assert out.stat().st_size <= target


def test_image_target_bigger(photo, tmp_path):
    target = 3 * MB
    out = run_conversion(photo, tmp_path, "image", {"format": "jpg", "target_bytes": target})
    size = out.stat().st_size
    assert target * 0.8 <= size <= target
    assert Image.open(out).width > 1600


def test_image_resize_and_ico(photo, tmp_path):
    out = run_conversion(photo, tmp_path, "image", {"format": "webp", "width": 400})
    assert Image.open(out).size == (400, 250)
    ico = run_conversion(photo, tmp_path, "image", {"format": "ico"})
    assert ico.suffix == ".ico"


def test_archive(photo, tmp_path):
    out = run_conversion(photo, tmp_path, "other", {"format": "zip"})
    assert out.name == "foto.png.zip"
    (tmp_path / "x").mkdir()
    out2 = run_conversion(out, tmp_path / "x", "archive", {"format": "tar.gz"})
    assert out2.name == "foto.png.tar.gz"


@needs_lo
def test_document_to_pdf_and_docx(tmp_path):
    md = tmp_path / "notitie.md"
    md.write_text("# Titel\n\nTekst met **vet**.\n")
    pdf = run_conversion(md, tmp_path, "document", {"format": "pdf"})
    assert pdf.read_bytes()[:4] == b"%PDF"
    docx = run_conversion(md, tmp_path, "document", {"format": "docx"})
    assert docx.stat().st_size > 1000
    png = run_conversion(pdf, tmp_path, "pdf", {"format": "png"})
    assert png.suffix == ".png"


@needs_lo
def test_pdf_compress_with_images(photo, tmp_path):
    big = tmp_path / "groot.pdf"
    im = Image.open(photo).convert("RGB").resize((3200, 2000))
    im.save(big, "PDF", resolution=300, quality=100)
    out = run_conversion(big, tmp_path, "pdf", {"format": "pdf", "quality": "low"})
    assert out.stat().st_size < big.stat().st_size
