"""Tekst, broncode, opmaaktalen, NFO-art, manpagina's en webpagina's.

- code: met kleuren (Pygments) naar HTML, PDF of PNG; naar Markdown of platte tekst
- Markdown/reStructuredText/AsciiDoc/Org/LaTeX: met pandoc (als die er is) naar Word, EPUB, HTML, PDF;
  zonder pandoc Markdown via de eigen omzetter
- .nfo/.diz: oude DOS-tekens (CP437) goed lezen, ASCII-art als afbeelding
- manpagina's (.1 t/m .9): via mandoc/groff als die er zijn, anders eenvoudig opgeschoond
- webpagina's (html, mhtml, webarchive): naar PDF (Chrome/Edge of ingebouwd), tekst, Markdown
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

from .util import NO_WINDOW, ConversionError, have

MARKUP = {"md", "markdown", "mdx", "rst", "adoc", "asciidoc", "org", "tex", "textile", "rmd"}
PANDOC_FROM = {"md": "markdown", "markdown": "markdown", "mdx": "markdown", "rmd": "markdown", "rst": "rst",
               "adoc": "asciidoc", "asciidoc": "asciidoc", "org": "org", "tex": "latex", "textile": "textile",
               "html": "html", "htm": "html", "opml": "opml"}
NFO = {"nfo", "diz"}
MAN = {str(i) for i in range(1, 10)} | {"man"}
WEB = {"html", "htm", "xhtml", "shtml", "mhtml", "mht", "webarchive"}


_PANDOC_IN: set[str] | None = None


def pandoc_inputs() -> set[str]:
    global _PANDOC_IN
    if _PANDOC_IN is None:
        try:
            r = subprocess.run(["pandoc", "--list-input-formats"], capture_output=True, text=True, timeout=20,
                               **NO_WINDOW)
            _PANDOC_IN = set(r.stdout.split())
        except Exception:  # noqa: BLE001
            _PANDOC_IN = set()
    return _PANDOC_IN


def read_text(path: Path) -> str:
    data = path.read_bytes()
    ext = path.suffix.lower().lstrip(".")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")
    if ext in NFO:
        return data.decode("cp437", "replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def targets(ext: str) -> list[str]:
    if ext in NFO:
        return ["png", "txt", "pdf", "html"]
    if ext in MAN:
        return ["txt", "html", "pdf"]
    if ext in WEB:
        return ["pdf", "png", "txt", "md", "html"] if ext in ("mhtml", "mht", "webarchive") else ["pdf", "png", "txt", "md"]
    if ext in MARKUP:
        out = ["html", "pdf", "docx", "txt"]
        if have("pandoc") and PANDOC_FROM.get(ext) in pandoc_inputs():
            out += ["epub", "odt", "rtf", "md", "rst", "tex"]
        return [t for t in out if t != ext]
    return ["pdf", "html", "png", "txt", "md"]


# --------------------------------------------------------------------------- hulpjes

def _font_path() -> Path | None:
    """Ons eigen monospace-lettertype (AC Mono, met kaderlijnen en blokken) als TTF voor Pillow."""
    import tempfile
    out = Path(tempfile.gettempdir()) / "ac-mono-regular.ttf"
    if out.exists():
        return out
    for cand in (Path(__file__).resolve().parent.parent / "static" / "fonts" / "ac-mono-Regular.woff2",):
        if cand.exists():
            try:
                from fontTools.ttLib import TTFont
                f = TTFont(str(cand))
                f.flavor = None
                f.save(str(out))
                return out
            except Exception:  # noqa: BLE001
                return None
    return None


def render_png(text: str, dst: Path, fg=(166, 255, 92), bg=(0, 0, 0)) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    lines = text.expandtabs(4).splitlines() or [""]
    lines = lines[:4000]
    fp = _font_path()
    size = 16
    font = ImageFont.truetype(str(fp), size) if fp else ImageFont.load_default()
    bbox = font.getbbox("M")
    cw = max(1, round(font.getlength("M")))
    ch = round((bbox[3] - bbox[1]) * 1.45) or 18
    width = min(4000, max(len(x) for x in lines) * cw + 40)
    height = min(30000, len(lines) * ch + 40)
    im = Image.new("RGB", (max(width, 80), max(height, 40)), bg)
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        y = 20 + i * ch
        if y > height:
            break
        d.text((20, y), line, font=font, fill=fg)
    im.save(dst, optimize=True)
    return dst


def highlight_html(text: str, filename: str, full: bool = True) -> str:
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_for_filename, guess_lexer
    try:
        lexer = get_lexer_for_filename(filename, text)
    except Exception:  # noqa: BLE001
        try:
            lexer = guess_lexer(text[:5000])
        except Exception:  # noqa: BLE001
            lexer = TextLexer()
    fmt = HtmlFormatter(full=full, noclasses=True, style="default", linenos=False, title=filename,
                        prestyles="font-size:9pt;line-height:1.3;white-space:pre-wrap")
    return highlight(text, lexer, fmt)


def markdown_html(md: str) -> str:
    """Kleine Markdown-omzetter (koppen, lijsten, code, vet/cursief, links, tabellen)."""
    out, in_code, in_list, table = [], False, False, []

    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", t)
        t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"[afbeelding: \1]", t)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)

    def flush_table():
        if table:
            rows = [r for r in table if not re.match(r"^\|?\s*:?-+", r.strip("| "))]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            out.append("<table>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                                           for r in cells) + "</table>")
            table.clear()

    for line in md.splitlines():
        if line.strip().startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.strip().startswith("|"):
            table.append(line)
            continue
        flush_table()
        m = re.match(r"(#{1,6})\s+(.*)", line)
        lm = re.match(r"\s*([-*+]|\d+\.)\s+(.*)", line)
        if lm:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(lm.group(2))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if m:
            n = min(len(m.group(1)), 4)
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> '))}</blockquote>")
        elif re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr/>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush_table()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def man_text(path: Path) -> str:
    for tool in (["mandoc", "-T", "utf8"], ["groff", "-man", "-T", "utf8"]):
        if have(tool[0]):
            r = subprocess.run([*tool, str(path)], capture_output=True, **NO_WINDOW)
            if r.returncode == 0 and r.stdout:
                return re.sub(r".\x08", "", r.stdout.decode("utf-8", "replace"))
    # zonder hulpprogramma: roff-opdrachten weghalen
    out = []
    for line in read_text(path).splitlines():
        if line.startswith((".\\\"", "'\\\"")):
            continue
        m = re.match(r"^\.(SH|SS)\s+(.*)", line)
        if m:
            out.append("\n" + m.group(2).strip('"').upper())
            continue
        if line.startswith("."):
            m = re.match(r"^\.(B|I|BR|IR|RB|BI|IB)\s+(.*)", line)
            if m:
                out.append(m.group(2).replace('"', ""))
            elif line.startswith(".TH"):
                out.append(" ".join(line.split()[1:3]).replace('"', ""))
            continue
        out.append(re.sub(r"\\f[BIRP]|\\\(..|\\-|\\&", lambda x: "-" if x.group() == "\\-" else "", line))
    return "\n".join(out).strip() + "\n"


def web_html(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in ("mhtml", "mht"):
        import email
        from email import policy
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        part = next((p for p in msg.walk() if p.get_content_type() == "text/html"), None)
        if not part:
            raise ConversionError("Geen webpagina gevonden in dit MHTML-bestand.")
        return part.get_content()
    if ext == "webarchive":
        import plistlib
        data = plistlib.loads(path.read_bytes())
        main = data.get("WebMainResource", {})
        raw = main.get("WebResourceData", b"")
        return raw.decode(main.get("WebResourceTextEncodingName") or "utf-8", "replace")
    return read_text(path)


def html_text(page: str) -> str:
    from .ebook import html_to_text
    return html_to_text(re.sub(r"(?is)<head.*?</head>", "", page))


def html_markdown(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", page)
    for n in range(1, 7):
        page = re.sub(rf"(?is)<h{n}[^>]*>(.*?)</h{n}>", lambda m, n=n: "\n" + "#" * n + " " + m.group(1) + "\n", page)
    page = re.sub(r"(?is)<(b|strong)[^>]*>(.*?)</\1>", r"**\2**", page)
    page = re.sub(r"(?is)<(i|em)[^>]*>(.*?)</\1>", r"*\2*", page)
    page = re.sub(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", page)
    page = re.sub(r"(?is)<li[^>]*>", "\n- ", page)
    from .ebook import html_to_text
    return html_to_text(page)


def chrome_pdf(src_html: Path, dst: Path, fmt: str = "pdf") -> bool:
    from .webshot import chromium, no_sandbox
    exe = chromium()
    if not exe:
        return False
    import tempfile
    prof = tempfile.mkdtemp(prefix="ac-chrome-")
    try:
        args = [exe, "--headless=new", "--disable-gpu", *no_sandbox(), "--no-first-run", f"--user-data-dir={prof}",
                "--allow-file-access-from-files"]
        args += ([f"--print-to-pdf={dst}", "--no-pdf-header-footer"] if fmt == "pdf" else
                 [f"--screenshot={dst}", "--window-size=1280,2000", "--hide-scrollbars"])
        subprocess.run([*args, src_html.resolve().as_uri()], capture_output=True, timeout=45, **NO_WINDOW)
    except Exception:  # noqa: BLE001
        return False
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    return dst.exists() and dst.stat().st_size > 0


# --------------------------------------------------------------------------- omzetten

def convert(src: Path, out_dir: Path, fmt: str, opts: dict) -> Path:
    ext = src.suffix.lower().lstrip(".")
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt == ext else ''}.{fmt}"
    from .pdftools import html_to_pdf, text_to_document

    if ext in WEB:
        page = web_html(src)
        if fmt == "html":
            dst.write_text(page, encoding="utf-8")
        elif fmt == "txt":
            dst.write_text(html_text(page) + "\n", encoding="utf-8")
        elif fmt == "md":
            dst.write_text(html_markdown(page) + "\n", encoding="utf-8")
        elif fmt in ("pdf", "png"):
            tmp = out_dir / "_pagina.html"
            tmp.write_text(page, encoding="utf-8")
            if not chrome_pdf(tmp if ext in ("mhtml", "mht", "webarchive") else src, dst, fmt):
                if fmt == "png":
                    raise ConversionError("Een afbeelding van een webpagina maken vraagt Chrome of Edge.")
                body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", page)
                html_to_pdf(body, dst)
            tmp.unlink(missing_ok=True)
        else:
            raise ConversionError(f"Webpagina naar .{fmt} wordt niet ondersteund.")
        return dst

    if ext in MAN:
        text = man_text(src)
        if fmt == "txt":
            dst.write_text(text, encoding="utf-8")
        elif fmt == "html":
            dst.write_text(f"<!doctype html><meta charset='utf-8'><pre>{html.escape(text)}</pre>", encoding="utf-8")
        else:
            html_to_pdf(f"<pre>{html.escape(text)}</pre>", dst)
        return dst

    text = read_text(src)
    if fmt == "txt":
        dst.write_text(text, encoding="utf-8")  # o.a. NFO's van CP437 naar UTF-8
        return dst
    if fmt == "png":
        return render_png(text, dst)
    if ext in MARKUP and have("pandoc") and fmt in ("html", "docx", "epub", "odt", "rtf", "md", "rst", "tex", "pdf"):
        if fmt != "pdf":
            subprocess.run(["pandoc", str(src), "-f", PANDOC_FROM.get(ext, "markdown"), "-o", str(dst),
                            "--standalone"], capture_output=True, timeout=300, check=False, **NO_WINDOW)
            if dst.exists():
                return dst
        else:
            r = subprocess.run(["pandoc", str(src), "-f", PANDOC_FROM.get(ext, "markdown"), "-t", "html"],
                               capture_output=True, timeout=300, **NO_WINDOW)
            if r.returncode == 0:
                return html_to_pdf(r.stdout.decode("utf-8", "replace"), dst)
    if ext in ("md", "markdown", "mdx", "rmd"):
        body = markdown_html(re.sub(r"(?m)^(import|export) .*$", "", text) if ext == "mdx" else text)
        if fmt == "html":
            dst.write_text(f"<!doctype html><meta charset='utf-8'><title>{html.escape(src.stem)}</title>{body}\n",
                           encoding="utf-8")
            return dst
        if fmt == "pdf":
            return html_to_pdf(body, dst)
        if fmt == "docx":
            return _html_docx(body, dst)
    if fmt == "md":
        lang = ext if ext not in NFO else ""
        dst.write_text(f"# {src.name}\n\n```{lang}\n{text.rstrip()}\n```\n", encoding="utf-8")
        return dst
    if fmt == "html":
        dst.write_text(highlight_html(text, src.name), encoding="utf-8")
        return dst
    if fmt == "pdf":
        if ext in NFO:
            return html_to_pdf(f"<pre>{html.escape(text)}</pre>", dst)
        return html_to_pdf(highlight_html(text[:400000], src.name, full=False), dst)
    if fmt == "docx":
        return text_to_document(text, dst, "docx")
    raise ConversionError(f".{ext} naar .{fmt} wordt niet ondersteund.")


def _html_docx(body: str, dst: Path) -> Path:
    from docx import Document
    d = Document()
    for m in re.finditer(r"(?is)<(h\d|p|li|pre|blockquote)[^>]*>(.*?)</\1>", body):
        tag, inner = m.group(1).lower(), re.sub(r"<[^>]+>", "", m.group(2))
        inner = html.unescape(inner)
        if tag.startswith("h"):
            d.add_heading(inner, min(int(tag[1]), 4))
        elif tag == "li":
            d.add_paragraph(inner, style="List Bullet")
        else:
            d.add_paragraph(inner)
    d.save(dst)
    return dst

