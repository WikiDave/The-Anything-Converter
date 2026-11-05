"""Nieuwe formaten: PDF-gereedschap, OCR-uitvoer, e-books, 7z, extra audio/video/afbeelding, checksums."""
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from converter import archive, ebook, hashes, image, media, pdftools
from converter.jobs import run_conversion

fitz = pytest.importorskip("fitz")


def make_pdf(path: Path, pages=2) -> Path:
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Hoofdstuk {n + 1}", fontsize=20)
        page.insert_text((72, 110), "Dit is een test van de Anything Converter.", fontsize=11)
        if n == 0:  # kleine tabel
            y = 160
            for row in (["Naam", "Aantal"], ["Appels", "12"], ["Peren", "7"]):
                page.insert_text((72, y), row[0]); page.insert_text((250, y), row[1])
                page.draw_line((70, y + 4), (330, y + 4))
                y += 20
    doc.save(path)
    return path


@pytest.mark.parametrize("fmt", ["docx", "xlsx", "pptx", "rtf", "txt", "html", "xml", "png", "jpg"])
def test_pdf_to_everything(tmp_path, fmt):
    src = make_pdf(tmp_path / "doc.pdf")
    out = run_conversion(src, tmp_path, "pdf", {"format": fmt})
    assert out.exists() and out.stat().st_size > 50
    if fmt == "docx":
        from docx import Document
        assert "Hoofdstuk 1" in "\n".join(p.text for p in Document(out).paragraphs)
    if fmt == "txt":
        assert "Anything Converter" in out.read_text()
    if fmt in ("png", "jpg"):
        assert out.suffix == ".zip" and len(zipfile.ZipFile(out).namelist()) == 2
    if fmt == "xml":
        assert out.read_text().count("<page ") == 2


@pytest.mark.parametrize("name,content", [("a.txt", "Hallo wereld\n\nTweede alinea"),
                                          ("a.rtf", r"{\rtf1\ansi Hallo {\b vet} wereld\par Tweede}"),
                                          ("a.md", "# Titel\n\nTekst met **vet**.")])
def test_documents_to_pdf_without_libreoffice(tmp_path, name, content):
    src = tmp_path / name
    src.write_text(content)
    out = pdftools.document_to_pdf(src, tmp_path / "uit.pdf")
    text = fitz.open(out)[0].get_text()
    assert "Hallo" in text or "Titel" in text


def test_docx_xlsx_to_pdf_without_libreoffice(tmp_path):
    from docx import Document
    from openpyxl import Workbook
    d = Document(); d.add_heading("Rapport", 1); d.add_paragraph("Inhoud van het rapport."); d.save(tmp_path / "r.docx")
    wb = Workbook(); wb.active.append(["Product", "Prijs"]); wb.active.append(["Thee", 2.5]); wb.save(tmp_path / "t.xlsx")
    assert "Inhoud" in fitz.open(pdftools.document_to_pdf(tmp_path / "r.docx", tmp_path / "r.pdf"))[0].get_text()
    assert "Thee" in fitz.open(pdftools.document_to_pdf(tmp_path / "t.xlsx", tmp_path / "t.pdf"))[0].get_text()


def test_text_to_documents(tmp_path):
    for fmt in ("txt", "docx", "rtf", "xlsx"):
        out = pdftools.text_to_document("Regel een  12\n\nRegel twee  7", tmp_path / f"x.{fmt}", fmt)
        assert out.stat().st_size > 10


@pytest.mark.parametrize("fmt", ["svg", "eps", "tga", "wbmp", "exr", "hdr"])
def test_extra_image_formats(tmp_path, fmt):
    src = tmp_path / "f.png"
    Image.new("RGB", (64, 40), (200, 30, 30)).save(src)
    out = image.process(src, tmp_path, {"format": fmt})
    assert out.exists() and out.stat().st_size > 20
    if fmt == "wbmp":
        assert out.read_bytes()[:4] == b"\x00\x00\x40\x28"


@pytest.mark.parametrize("fmt", ["aiff", "wma", "m4r", "mmf"])
def test_extra_audio_formats(tmp_path, fmt):
    import math, struct, wave
    src = tmp_path / "t.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(i / 8))) for i in range(22050)))
    out = media.process(src, tmp_path, {"format": fmt})
    assert out.exists() and out.stat().st_size > 100


@pytest.mark.parametrize("fmt", ["wmv", "flv", "mpg", "ogv", "3gp"])
def test_extra_video_formats(tmp_path, fmt):
    import subprocess
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-f", "lavfi",
                    "-i", "sine", "-t", "1", "-pix_fmt", "yuv420p", "-shortest", str(src)], check=True)
    out = media.process(src, tmp_path, {"format": fmt, "quality": "low"})
    assert out.exists() and out.stat().st_size > 1000


def test_device_preset_limits_height(tmp_path):
    import subprocess
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x480:rate=10", "-t", "1",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    out = media.process(src, tmp_path, {"format": "mp4", "device": "psp", "quality": "low"})
    from converter.util import ffprobe
    v = next(s for s in ffprobe(out)["streams"] if s["codec_type"] == "video")
    assert v["height"] == 272


def test_7z_roundtrip(tmp_path):
    pytest.importorskip("py7zr")
    src = tmp_path / "a.txt"
    src.write_text("hallo" * 100)
    (tmp_path / "o").mkdir()
    out = archive.process(src, tmp_path / "o", {"format": "7z"})
    assert out.suffix == ".7z"
    back = archive.process(out, tmp_path / "o", {"format": "zip"})
    assert zipfile.ZipFile(back).read("a.txt") == b"hallo" * 100


def test_epub_roundtrip_without_calibre(tmp_path, monkeypatch):
    monkeypatch.setattr(ebook, "calibre", lambda: None)
    src = tmp_path / "boek.txt"
    src.write_text("Eerste hoofdstuk.\n\nTweede alinea van het boek.")
    epub = ebook.write_epub(src, tmp_path / "boek.epub")
    title, body = ebook.read_epub(epub)
    assert title == "boek" and "Tweede alinea" in body
    outdir = tmp_path / "uit"
    outdir.mkdir()
    for fmt in ("txt", "html", "pdf", "docx"):
        out = ebook.convert(epub, outdir, fmt, {})
        assert out.stat().st_size > 20
    with pytest.raises(Exception, match="Calibre"):
        ebook.convert(epub, tmp_path, "mobi", {})


def test_hashes(tmp_path):
    p = tmp_path / "x"
    p.write_bytes(b"abc")
    h = hashes.compute(p)
    assert h["MD5"] == "900150983cd24fb0d6963f7d28e17f72"
    assert h["SHA-256"].startswith("ba7816bf")
    assert h["CRC-32"] == "352441c2"
    assert "HMAC" not in h and len(hashes.compute(p, "sleutel")) >= 5


def test_ocr_image_when_available(tmp_path):
    from converter import ocr
    if not ocr.available():
        pytest.skip("geen OCR op deze machine")
    im = Image.new("RGB", (900, 200), "white")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    d.text((30, 50), "Anything Converter", fill="black", font=font)
    src = tmp_path / "tekst.png"
    im.save(src)
    out = run_conversion(src, tmp_path, "image", {"format": "txt"})
    assert "Converter" in out.read_text()
