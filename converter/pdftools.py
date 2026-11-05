"""PDF omzetten zonder LibreOffice: naar Word, Excel, PowerPoint, afbeeldingen, RTF, TXT, HTML en XML
(PyMuPDF), en documenten via HTML terug naar PDF (PyMuPDF Story) als LibreOffice ontbreekt.
"""
from __future__ import annotations

import html
import io
import re
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .util import ConversionError

ProgressFn = Callable[[float, str], None]
PDF_OUT = {"docx", "xlsx", "pptx", "png", "jpg", "rtf", "txt", "html", "xml"}
FALLBACK_IN = {"txt", "md", "markdown", "html", "htm", "rtf", "docx", "xlsx", "pptx"}


def have_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ConversionError("PyMuPDF is missing (pip install pymupdf).") from e
    return fitz


def _tick(progress, i, n, label):
    if progress:
        progress(0.1 + 0.85 * (i + 1) / max(n, 1), f"{label} {i + 1}/{n}")


def convert_pdf(src: Path, out_dir: Path, fmt: str, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    fitz = _fitz()
    try:
        doc = fitz.open(src)
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"PDF cannot be opened: {e}") from e
    if doc.needs_pass:
        raise ConversionError("This PDF is password-protected.")
    dst = out_dir / f"{src.stem}.{fmt}"
    fn = {"docx": _to_docx, "xlsx": _to_xlsx, "pptx": _to_pptx, "png": _to_images, "jpg": _to_images,
          "rtf": _to_rtf, "txt": _to_txt, "html": _to_html, "xml": _to_xml}[fmt]
    return fn(doc, src, dst, fmt, opts, progress)


# --------------------------------------------------------------------- tekst (met OCR voor scans)

def page_text(page, ocr_fallback: bool = True) -> str:
    text = page.get_text("text", sort=True)
    if text.strip() or not ocr_fallback:
        return text
    # Gescande pagina zonder tekstlaag: OCR op een afbeelding van de pagina
    from . import ocr
    if not ocr.available():
        return ""
    png = page.get_pixmap(dpi=250).tobytes("png")
    return ocr.image_bytes(png)


def _to_txt(doc, src, dst, fmt, opts, progress):
    parts = []
    for i, page in enumerate(doc):
        parts.append(page_text(page).rstrip())
        _tick(progress, i, len(doc), "page")
    dst.write_text("\n\n\f".join(parts).strip() + "\n", encoding="utf-8")
    return dst


def _to_html(doc, src, dst, fmt, opts, progress):
    body = []
    for i, page in enumerate(doc):
        body.append(f'<section class="page" id="p{i + 1}">{page.get_text("html")}</section>')
        _tick(progress, i, len(doc), "page")
    dst.write_text(
        "<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>" + html.escape(src.stem) + "</title>"
        "<style>body{background:#888;margin:0;padding:16px}.page{margin:0 auto 16px;box-shadow:0 2px 8px #0005}"
        ".page>div{margin:0 auto}</style></head><body>\n" + "\n".join(body) + "\n</body></html>\n",
        encoding="utf-8")
    return dst


def _to_xml(doc, src, dst, fmt, opts, progress):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<document name="{html.escape(src.name)}" pages="{len(doc)}">']
    for i, page in enumerate(doc):
        xml = page.get_text("xml")
        xml = re.sub(r"^<\?xml[^>]*>\s*", "", xml)
        out.append(xml.replace("<page ", f'<page number="{i + 1}" ', 1))
        _tick(progress, i, len(doc), "page")
    out.append("</document>")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dst


def _to_images(doc, src, dst, fmt, opts, progress):
    dpi = {"high": 220, "medium": 150, "low": 100}.get(opts.get("quality") or "medium", 150)
    files = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        data = pix.tobytes("png") if fmt == "png" else pix.tobytes("jpg", jpg_quality=88)
        files.append((f"{src.stem}_page_{i + 1:03d}.{fmt}", data))
        _tick(progress, i, len(doc), "page")
    if len(files) == 1:
        dst.write_bytes(files[0][1])
        return dst
    zdst = dst.with_name(f"{src.stem}_paginas_{fmt}.zip")
    with zipfile.ZipFile(zdst, "w", zipfile.ZIP_STORED) as z:
        for name, data in files:
            z.writestr(name, data)
    return zdst


# --------------------------------------------------------------------- Word

def _blocks(page):
    """Tekst- en afbeeldingsblokken in leesvolgorde, met tabellen apart."""
    tables = []
    try:
        tables = [t for t in page.find_tables().tables if t.row_count > 1 and t.col_count > 1]
    except Exception:  # noqa: BLE001 - tabelherkenning is een extraatje
        tables = []
    boxes = [t.bbox for t in tables]

    def in_table(b):
        x0, y0, x1, y1 = b
        return any(x0 >= t[0] - 2 and y0 >= t[1] - 2 and x1 <= t[2] + 2 and y1 <= t[3] + 2 for t in boxes)

    items = []
    for b in page.get_text("dict", sort=True)["blocks"]:
        if in_table(b["bbox"]):
            continue
        items.append((b["bbox"][1], b["bbox"][0], "block", b))
    for t in tables:
        items.append((t.bbox[1], t.bbox[0], "table", t))
    items.sort(key=lambda it: (round(it[0] / 4), it[1]))
    return items


def _to_docx(doc, src, dst, fmt, opts, progress):
    try:
        from docx import Document
        from docx.enum.text import WD_BREAK
        from docx.shared import Emu, Pt, RGBColor
    except ImportError as e:
        raise ConversionError("python-docx is missing (pip install python-docx).") from e
    out = Document()
    sec = out.sections[0]
    if len(doc):
        w, h = doc[0].rect.width, doc[0].rect.height
        sec.page_width, sec.page_height = Emu(int(w * 12700)), Emu(int(h * 12700))
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, m, Emu(int(42 * 12700)))
    usable = sec.page_width - sec.left_margin - sec.right_margin
    body_size = 11.0
    for i, page in enumerate(doc):
        items = _blocks(page)
        if not any(kind == "table" or (kind == "block" and b.get("type") == 1) or
                   (kind == "block" and any(s["text"].strip() for ln in b.get("lines", []) for s in ln["spans"]))
                   for _, _, kind, b in items):
            # Scan: OCR-tekst, of anders de pagina als afbeelding
            text = page_text(page)
            if text.strip():
                for para in re.split(r"\n\s*\n", text):
                    out.add_paragraph(" ".join(para.split()))
            else:
                png = page.get_pixmap(dpi=150).tobytes("png")
                out.add_picture(io.BytesIO(png), width=usable)
        for _, _, kind, b in items:
            if kind == "table":
                rows = b.extract()
                ncols = max(len(r) for r in rows)
                tbl = out.add_table(rows=len(rows), cols=ncols)
                tbl.style = "Table Grid"
                for r, row in enumerate(rows):
                    for c, val in enumerate(row):
                        tbl.cell(r, c).text = (val or "").replace("\n", " ")
                out.add_paragraph()
                continue
            if b.get("type") == 1:  # afbeelding
                try:
                    img = b["image"]
                    width = min(usable, Emu(int((b["bbox"][2] - b["bbox"][0]) * 12700)))
                    out.add_picture(io.BytesIO(img), width=width)
                except Exception:  # noqa: BLE001 - vreemd beeldformaat: overslaan
                    pass
                continue
            para = out.add_paragraph()
            first = True
            for line in b.get("lines", []):
                if not first:
                    para.add_run(" ")
                first = False
                for span in line["spans"]:
                    t = span["text"]
                    if not t:
                        continue
                    run = para.add_run(t)
                    size = round(span["size"] * 2) / 2
                    if size and abs(size - body_size) > 0.6:
                        run.font.size = Pt(size)
                    flags = span["flags"]
                    run.bold = bool(flags & 16) or "Bold" in span["font"]
                    run.italic = bool(flags & 2) or "Italic" in span["font"]
                    col = span.get("color", 0)
                    if col:
                        run.font.color.rgb = RGBColor((col >> 16) & 255, (col >> 8) & 255, col & 255)
        if i < len(doc) - 1:
            out.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        _tick(progress, i, len(doc), "page")
    out.save(dst)
    return dst


# --------------------------------------------------------------------- Excel

def _to_xlsx(doc, src, dst, fmt, opts, progress):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as e:
        raise ConversionError("openpyxl is missing (pip install openpyxl).") from e
    wb = Workbook()
    wb.remove(wb.active)
    found = 0
    for i, page in enumerate(doc):
        try:
            tables = [t for t in page.find_tables().tables if t.row_count and t.col_count > 1]
        except Exception:  # noqa: BLE001
            tables = []
        for k, t in enumerate(tables):
            found += 1
            ws = wb.create_sheet(f"P{i + 1}" + (f"-{k + 1}" if len(tables) > 1 else ""))
            for row in t.extract():
                ws.append([_cell(v) for v in row])
            for c in ws[1]:
                c.font = Font(bold=True)
            _autowidth(ws)
        _tick(progress, i, len(doc), "page")
    if not found:
        # Geen herkenbare tabellen: elke regel een rij, kolommen op grote witruimtes
        ws = wb.create_sheet("Text")
        for i, page in enumerate(doc):
            for line in page_text(page).splitlines():
                if line.strip():
                    ws.append([_cell(v) for v in re.split(r"\s{2,}|\t", line.strip())])
        _autowidth(ws)
    wb.save(dst)
    return dst


def _cell(v):
    if v is None:
        return None
    v = str(v).replace("\n", " ").strip()
    num = v.replace("\u00a0", "").replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+", num):  # 1.234,56
        num = num.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})*\.\d+", num):  # 1,234.56
        num = num.replace(",", "")
    try:
        if re.fullmatch(r"-?\d+", num) and not (len(num) > 1 and num.lstrip("-").startswith("0")):
            return int(num)
        if re.fullmatch(r"-?\d+\.\d+", num):
            return float(num)
    except ValueError:
        pass
    return v


def _autowidth(ws):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(60, max(8, width + 2))


# --------------------------------------------------------------------- PowerPoint

def _to_pptx(doc, src, dst, fmt, opts, progress):
    try:
        from pptx import Presentation
        from pptx.util import Emu
    except ImportError as e:
        raise ConversionError("python-pptx is missing (pip install python-pptx).") from e
    prs = Presentation()
    if len(doc):
        w, h = doc[0].rect.width, doc[0].rect.height
        prs.slide_width, prs.slide_height = Emu(int(w * 12700)), Emu(int(h * 12700))
    blank = prs.slide_layouts[6]
    for i, page in enumerate(doc):
        slide = prs.slides.add_slide(blank)
        png = page.get_pixmap(dpi=170, alpha=False).tobytes("png")
        slide.shapes.add_picture(io.BytesIO(png), 0, 0, prs.slide_width, prs.slide_height)
        text = page.get_text("text", sort=True).strip()
        if text:  # tekst in de notities, zodat hij doorzoekbaar en kopieerbaar blijft
            slide.notes_slide.notes_text_frame.text = text
        _tick(progress, i, len(doc), "dia")
    prs.save(dst)
    return dst


# --------------------------------------------------------------------- RTF

def _rtf_escape(t: str) -> str:
    out = []
    for ch in t:
        o = ord(ch)
        if ch in "\\{}":
            out.append("\\" + ch)
        elif o < 128:
            out.append(ch)
        else:
            out.append(f"\\u{o if o < 32768 else o - 65536}?")
    return "".join(out)


def _to_rtf(doc, src, dst, fmt, opts, progress):
    parts = [r"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fswiss Helvetica;}}\fs22"]
    for i, page in enumerate(doc):
        blocks = page.get_text("dict", sort=True)["blocks"]
        texts = [b for b in blocks if b.get("type") == 0]
        if not texts:
            for para in re.split(r"\n\s*\n", page_text(page)):
                if para.strip():
                    parts.append(r"\pard " + _rtf_escape(" ".join(para.split())) + r"\par")
        for b in texts:
            runs = []
            for line in b["lines"]:
                for span in line["spans"]:
                    t = span["text"]
                    if not t:
                        continue
                    bold = bool(span["flags"] & 16) or "Bold" in span["font"]
                    ital = bool(span["flags"] & 2) or "Italic" in span["font"]
                    size = int(round(span["size"] * 2))
                    runs.append("{" + (r"\b" if bold else "") + (r"\i" if ital else "") + f"\\fs{size} "
                                + _rtf_escape(t) + "}")
                runs.append(" ")
            parts.append(r"\pard " + "".join(runs).rstrip() + r"\par")
        if i < len(doc) - 1:
            parts.append(r"\page")
        _tick(progress, i, len(doc), "page")
    parts.append("}")
    dst.write_text("\n".join(parts), encoding="ascii", errors="replace")
    return dst


# --------------------------------------------------------------------- naar PDF zonder LibreOffice

CSS = ("body{font-family:sans-serif;font-size:11pt;line-height:1.35}"
       "h1{font-size:20pt}h2{font-size:16pt}h3{font-size:13pt}"
       "table{border-collapse:collapse}td,th{border:0.5pt solid #888;padding:2pt 4pt;font-size:9pt}"
       "pre{font-family:monospace;font-size:9pt;white-space:pre-wrap}")


def html_to_pdf(body_html: str, dst: Path, landscape: bool = False) -> Path:
    fitz = _fitz()
    rect = fitz.paper_rect("a4-l" if landscape else "a4")
    where = rect + (42, 42, -42, -42)
    story = fitz.Story(html=body_html, user_css=CSS)
    writer = fitz.DocumentWriter(str(dst))
    more = True
    while more:
        dev = writer.begin_page(rect)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return dst


def rtf_to_text(data: str) -> str:
    """Eenvoudige RTF-lezer: tekst met alinea's (opmaak gaat verloren)."""
    out, stack, skip = [], [], False
    i, n = 0, len(data)
    ignorable = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "*", "listtable",
                 "listoverridetable", "rsidtbl", "generator", "themedata", "colorschememapping", "latentstyles",
                 "datastore", "xmlnstbl", "mmathPr"}
    while i < n:
        ch = data[i]
        if ch == "{":
            stack.append(skip)
            i += 1
        elif ch == "}":
            skip = stack.pop() if stack else False
            i += 1
        elif ch == "\\":
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)", data[i:])
            if not m:
                i += 1
                continue
            word, arg, hexc, sym = m.groups()
            i += m.end()
            if skip:
                continue
            if hexc:
                out.append(bytes([int(hexc, 16)]).decode("cp1252", "replace"))
            elif sym:
                if sym == "*":
                    skip = True
                elif sym in "\\{}":
                    out.append(sym)
                elif sym == "~":
                    out.append("\u00a0")
            elif word in ignorable:
                skip = True
            elif word in ("par", "line", "sect", "page"):
                out.append("\n")
            elif word == "tab":
                out.append("\t")
            elif word == "u" and arg:
                code = int(arg)
                out.append(chr(code + 65536 if code < 0 else code))
                if i < n and data[i] == "?":
                    i += 1
        elif ch in "\r\n":
            i += 1
        else:
            if not skip:
                out.append(ch)
            i += 1
    return "".join(out)


def _paras_html(text: str) -> str:
    paras = [p for p in re.split(r"\n\s*\n|\n", text)]
    return "".join(f"<p>{html.escape(p)}</p>" if p.strip() else "" for p in paras)


def document_to_pdf(src: Path, dst: Path) -> Path:
    """Word/Excel/PowerPoint/RTF/TXT/Markdown/HTML naar PDF zonder LibreOffice (eenvoudige opmaak)."""
    ext = src.suffix.lower().lstrip(".")
    landscape = False
    if ext == "txt":
        body = "<pre>" + html.escape(src.read_text(encoding="utf-8", errors="replace")) + "</pre>"
    elif ext in ("md", "markdown"):
        body = _markdown_html(src.read_text(encoding="utf-8", errors="replace"))
    elif ext in ("html", "htm"):
        body = src.read_text(encoding="utf-8", errors="replace")
    elif ext == "rtf":
        body = _paras_html(rtf_to_text(src.read_text(encoding="latin-1", errors="replace")))
    elif ext == "docx":
        body = _docx_html(src)
    elif ext == "xlsx":
        body, landscape = _xlsx_html(src), True
    elif ext == "pptx":
        body, landscape = _pptx_html(src), True
    else:
        raise ConversionError(f".{ext} to PDF needs LibreOffice (free: libreoffice.org).")
    return html_to_pdf(body, dst, landscape)


def _markdown_html(md: str) -> str:
    out = []
    for line in md.splitlines():
        m = re.match(r"(#{1,3})\s+(.*)", line)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{html.escape(m.group(2))}</h{n}>")
        elif re.match(r"\s*[-*]\s+", line):
            out.append("<p>• " + html.escape(re.sub(r"^\s*[-*]\s+", "", line)) + "</p>")
        elif line.strip():
            t = html.escape(line)
            t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
            t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
            out.append(f"<p>{t}</p>")
    return "".join(out)


def _docx_html(src: Path) -> str:
    from docx import Document
    d = Document(src)
    out = []
    body = d.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            style = (p.style.name if p.style is not None else "") or ""
            runs = []
            for r in p.runs:
                t = html.escape(r.text)
                if r.bold:
                    t = f"<b>{t}</b>"
                if r.italic:
                    t = f"<i>{t}</i>"
                runs.append(t)
            text = "".join(runs)
            m = re.match(r"(Heading|Kop)\s*(\d)", style)
            if m:
                lvl = min(3, int(m.group(2)))
                out.append(f"<h{lvl}>{text}</h{lvl}>")
            elif style.lower().startswith("title") or style.lower().startswith("titel"):
                out.append(f"<h1>{text}</h1>")
            elif "List" in style or "Lijst" in style:
                out.append(f"<p>• {text}</p>")
            else:
                out.append(f"<p>{text or '&nbsp;'}</p>")
        elif tag == "tbl":
            t = Table(child, d)
            rows = "".join("<tr>" + "".join(f"<td>{html.escape(c.text)}</td>" for c in row.cells) + "</tr>"
                           for row in t.rows)
            out.append(f"<table>{rows}</table>")
    return "".join(out)


def _xlsx_html(src: Path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(src, data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"<h2>{html.escape(ws.title)}</h2><table>")
        for row in ws.iter_rows(values_only=True):
            if all(v is None for v in row):
                continue
            out.append("<tr>" + "".join(f"<td>{'' if v is None else html.escape(str(v))}</td>" for v in row) + "</tr>")
        out.append("</table>")
    return "".join(out)


def _pptx_html(src: Path) -> str:
    from pptx import Presentation
    prs = Presentation(src)
    out = []
    for n, slide in enumerate(prs.slides, 1):
        out.append(f"<h2>Dia {n}</h2>")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    t = "".join(r.text for r in p.runs)
                    if t.strip():
                        out.append(f"<p>{html.escape(t)}</p>")
    return "".join(out)


def text_to_document(text: str, dst: Path, fmt: str) -> Path:
    """Herkende tekst (OCR/spraak) opslaan als txt, docx, rtf of xlsx."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if fmt == "txt":
        dst.write_text(text.strip() + "\n", encoding="utf-8")
    elif fmt == "docx":
        from docx import Document
        d = Document()
        for p in paras:
            d.add_paragraph(p)
        d.save(dst)
    elif fmt == "rtf":
        body = "".join(r"\pard " + _rtf_escape(p).replace("\n", r"\line ") + r"\par" + "\n" for p in paras)
        dst.write_text(r"{\rtf1\ansi\deff0{\fonttbl{\f0\fswiss Helvetica;}}\fs22" + "\n" + body + "}",
                       encoding="ascii", errors="replace")
    elif fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Text"
        for line in text.splitlines():
            if line.strip():
                ws.append([_cell(v) for v in re.split(r"\s{2,}|\t", line.strip())])
        _autowidth(ws)
        wb.save(dst)
    else:
        raise ConversionError(f"Text to .{fmt} is not supported.")
    return dst


# --------------------------------------------------------------------- PDF-werkbank (terminal/CLI)

def parse_pages(spec: str, count: int) -> list[int]:
    """'1-3,5,8-' -> [0,1,2,4,7,...] (0-gebaseerd). Leeg = alle pagina's."""
    spec = (spec or "").replace(" ", "")
    if not spec:
        return list(range(count))
    out: list[int] = []
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo = int(a) if a else 1
            hi = int(b) if b else count
        else:
            lo = hi = int(part)
        if lo < 1 or hi > count or lo > hi:
            raise ConversionError(f"Pages '{part}' do not exist (1-{count}).")
        out.extend(range(lo - 1, hi))
    return out


def merge(files: list[Path], dst: Path) -> Path:
    """PDF's en afbeeldingen samenvoegen tot één PDF, in de gegeven volgorde."""
    fitz = _fitz()
    out = fitz.open()
    for f in files:
        if f.suffix.lower() == ".pdf":
            with fitz.open(f) as d:
                if d.needs_pass:
                    raise ConversionError(f"{f.name} is password-protected.")
                out.insert_pdf(d)
        else:
            with fitz.open(f) as img:
                pdf = fitz.open("pdf", img.convert_to_pdf())
                out.insert_pdf(pdf)
    if not len(out):
        raise ConversionError("No pages to merge.")
    out.save(dst, garbage=3, deflate=True)
    return dst


def split(src: Path, out_dir: Path, spec: str = "") -> Path:
    """Elke pagina een eigen PDF (zip), of alleen de gekozen pagina's als één PDF."""
    fitz = _fitz()
    doc = fitz.open(src)
    if spec.strip():
        dst = out_dir / f"{src.stem}_pages-{spec.replace(',', '_')}.pdf"
        new = fitz.open()
        for i in parse_pages(spec, len(doc)):
            new.insert_pdf(doc, from_page=i, to_page=i)
        new.save(dst, garbage=3, deflate=True)
        return dst
    dst = out_dir / f"{src.stem}_losse-paginas.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(len(doc)):
            one = fitz.open()
            one.insert_pdf(doc, from_page=i, to_page=i)
            z.writestr(f"{src.stem}_page_{i + 1:03d}.pdf", one.tobytes(garbage=3, deflate=True))
    return dst


def edit_pages(src: Path, dst: Path, delete: str = "", rotate: str = "", angle: int = 90) -> Path:
    """Pagina's verwijderen en/of draaien."""
    fitz = _fitz()
    doc = fitz.open(src)
    for i in parse_pages(rotate, len(doc)) if rotate.strip() else []:
        doc[i].set_rotation((doc[i].rotation + angle) % 360)
    if delete.strip():
        doc.delete_pages(sorted(set(parse_pages(delete, len(doc)))))
    if not len(doc):
        raise ConversionError("No pages would be left.")
    doc.save(dst, garbage=3, deflate=True)
    return dst
