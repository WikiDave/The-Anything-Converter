"""E-books: EPUB, MOBI, AZW3, FB2, LIT, LRF, PDB, TCR.

Met Calibre (gratis, calibre-ebook.com) kan alles; de app vindt het vanzelf. Zonder Calibre:
EPUB/FB2 lezen naar TXT, HTML, PDF en DOCX, en documenten naar EPUB/FB2 via pandoc als dat er is.
"""
from __future__ import annotations

import html
import re
import shutil
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from .util import ConversionError, ProgressFn, have, run

EBOOK_OUT = ["epub", "mobi", "azw3", "fb2", "pdf", "docx", "txt", "html", "rtf", "lit", "lrf", "pdb", "tcr"]


def calibre() -> Optional[str]:
    found = shutil.which("ebook-convert")
    if found:
        return found
    for cand in ("/Applications/calibre.app/Contents/MacOS/ebook-convert",
                 r"C:\Program Files\Calibre2\ebook-convert.exe", r"C:\Program Files (x86)\Calibre2\ebook-convert.exe"):
        if Path(cand).exists():
            return cand
    return None


def convert(src: Path, out_dir: Path, fmt: str, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    ext = src.suffix.lower().lstrip(".")
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt == ext else ''}.{fmt}"
    tool = calibre()
    if tool:
        if progress:
            progress(0.2, "omzetten met Calibre")
        run([tool, str(src), str(dst)], timeout=1800)
        if not dst.exists():
            raise ConversionError("Calibre kon dit e-book niet omzetten.")
        return dst
    # Zonder Calibre
    if ext in ("epub", "fb2") and fmt in ("txt", "html", "pdf", "docx", "rtf"):
        title, body = read_epub(src) if ext == "epub" else read_fb2(src)
        if progress:
            progress(0.5, "e-book gelezen")
        if fmt == "html":
            dst.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
                           f"</head><body>{body}</body></html>\n", encoding="utf-8")
            return dst
        if fmt == "pdf":
            from .pdftools import html_to_pdf
            return html_to_pdf(body, dst)
        from .pdftools import text_to_document
        return text_to_document(html_to_text(body), dst, fmt)
    if fmt in ("epub", "fb2") and have("pandoc") and ext in ("docx", "odt", "md", "markdown", "html", "htm",
                                                            "txt", "epub", "fb2", "rtf"):
        cmd = ["pandoc", str(src), "-o", str(dst), "--standalone"]
        if ext == "txt":
            cmd += ["-f", "markdown"]
        run(cmd, timeout=600)
        return dst
    if fmt == "epub" and ext in ("txt", "html", "htm", "md", "markdown", "docx"):
        return write_epub(src, dst)
    raise ConversionError(f".{ext} naar .{fmt} heeft Calibre nodig (gratis, calibre-ebook.com). "
                          "Na installeren werkt het vanzelf.")


def html_to_text(body: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", body)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|h\d|li|tr|section|blockquote)>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def read_epub(src: Path) -> tuple[str, str]:
    with zipfile.ZipFile(src) as z:
        container = ET.fromstring(z.read("META-INF/container.xml"))
        opf_path = next(e.get("full-path") for e in container.iter() if e.tag.endswith("rootfile"))
        opf = ET.fromstring(z.read(opf_path))
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        manifest = {e.get("id"): e.get("href") for e in opf.iter() if e.tag.endswith("}item")}
        spine = [e.get("idref") for e in opf.iter() if e.tag.endswith("}itemref")]
        title = next((e.text for e in opf.iter() if e.tag.endswith("}title") and e.text), src.stem)
        parts = []
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            try:
                raw = z.read(base + href).decode("utf-8", "replace")
            except KeyError:
                continue
            m = re.search(r"(?is)<body[^>]*>(.*)</body>", raw)
            chunk = m.group(1) if m else raw
            chunk = re.sub(r"(?is)<img[^>]*>", "", chunk)  # afbeeldingen weglaten (paden kloppen niet meer)
            parts.append(f"<section>{chunk}</section>")
    return title, "\n".join(parts)


def read_fb2(src: Path) -> tuple[str, str]:
    root = ET.parse(src).getroot()

    def local(e):
        return e.tag.rsplit("}", 1)[-1]

    title = next(("".join(e.itertext()) for e in root.iter() if local(e) == "book-title"), src.stem)
    out = []
    for body in (e for e in root.iter() if local(e) == "body"):
        for e in body.iter():
            tag = local(e)
            text = html.escape("".join(e.itertext()).strip())
            if not text:
                continue
            if tag == "title":
                out.append(f"<h2>{text}</h2>")
            elif tag in ("p", "v", "subtitle"):
                out.append(f"<p>{text}</p>")
    return title, "\n".join(out)


def write_epub(src: Path, dst: Path) -> Path:
    """Eenvoudige EPUB uit tekst, HTML, Markdown of Word (zonder Calibre of pandoc)."""
    ext = src.suffix.lower().lstrip(".")
    if ext == "docx":
        from .pdftools import _docx_html
        body = _docx_html(src)
    elif ext in ("md", "markdown"):
        from .pdftools import _markdown_html
        body = _markdown_html(src.read_text(encoding="utf-8", errors="replace"))
    elif ext in ("html", "htm"):
        raw = src.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?is)<body[^>]*>(.*)</body>", raw)
        body = m.group(1) if m else raw
    else:
        body = "".join(f"<p>{html.escape(p)}</p>" for p in
                       re.split(r"\n\s*\n", src.read_text(encoding="utf-8", errors="replace")) if p.strip())
    # XHTML vereist: losse <br> en dergelijke dichtmaken
    body = re.sub(r"<(br|hr|img)([^>]*?)(?<!/)>", r"<\1\2/>", body)
    title = html.escape(src.stem)
    with zipfile.ZipFile(dst, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:'
                   'container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-'
                   'package+xml"/></rootfiles></container>', compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf",
                   f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" '
                   f'version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   f'<dc:identifier id="id">anything-converter-{abs(hash(src.name))}</dc:identifier>'
                   f'<dc:title>{title}</dc:title><dc:language>nl</dc:language>'
                   f'<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
                   f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                   f'<item id="c1" href="tekst.xhtml" media-type="application/xhtml+xml"/></manifest>'
                   f'<spine><itemref idref="c1"/></spine></package>', compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml",
                   f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
                   f'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{title}</title></head><body>'
                   f'<nav epub:type="toc"><ol><li><a href="tekst.xhtml">{title}</a></li></ol></nav></body></html>',
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/tekst.xhtml",
                   f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head>'
                   f'<title>{title}</title></head><body>{body}</body></html>', compress_type=zipfile.ZIP_DEFLATED)
    return dst

