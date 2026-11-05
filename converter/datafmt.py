"""Gestructureerde data: omzetten tussen JSON, YAML, TOML, XML, CSV, Excel, HTML en meer.

Ook: SQLite-databases, dBase (.dbf), NumPy-arrays, Jupyter-notebooks, HAR, RSS/Atom, OPML,
plist (macOS), INI/properties/.env, en bankbestanden (OFX/QFX/QBO, QIF, MT940, CODA).
Python-pickles worden bewust NIET geopend: die kunnen code uitvoeren.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .util import ConversionError

TREE = {"json", "json5", "jsonc", "jsonl", "ndjson", "jsonld", "geojson-data", "yaml", "yml", "toml", "xml", "xsd",
        "xsl", "xslt", "ini", "cfg", "conf", "properties", "env", "plist", "webmanifest", "npy", "npz", "msgpack",
        "csv", "tsv"}
DB = {"sqlite", "sqlite3", "db", "db3", "dbf"}
SPECIAL = {"ipynb", "har", "rss", "atom", "opml"}
FINANCE = {"ofx", "qfx", "qbo", "qif", "sta", "940", "cod"}
TREE_OUT = ["json", "yaml", "toml", "xml", "csv", "xlsx", "html", "txt"]


def targets(ext: str) -> list[str]:
    if ext in DB:
        return ["xlsx", "csv", "json", "sql", "html"] if ext != "dbf" else ["xlsx", "csv", "json", "html"]
    if ext == "ipynb":
        return ["html", "md", "py", "pdf", "txt"]
    if ext == "har":
        return ["csv", "xlsx", "json", "html"]
    if ext in ("rss", "atom"):
        return ["html", "csv", "json", "txt", "md"]
    if ext == "opml":
        return ["md", "txt", "html", "csv", "json"]
    if ext in FINANCE:
        return ["csv", "xlsx", "json", "html"]
    if ext == "plist":
        return ["json", "xml", "yaml", "plist", "txt"]
    if ext in ("npy", "npz"):
        return ["csv", "json", "xlsx", "txt"]
    if ext in ("ini", "cfg", "conf", "properties", "env"):
        return ["json", "yaml", "toml", "xml", "csv", "txt"]
    out = list(TREE_OUT)
    norm = {"yml": "yaml", "jsonl": "json", "ndjson": "json", "json5": "json", "jsonc": "json", "jsonld": "json",
            "webmanifest": "json", "xsd": "xml", "xsl": "xml", "xslt": "xml"}.get(ext, ext)
    if norm in ("json", "xml", "yaml"):
        out.append(f"{norm}-mooi")  # netjes inspringen
    return [t for t in out if t != norm]


# --------------------------------------------------------------------------- lezen

def _strip_json_comments(text: str) -> str:
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r",(\s*[}\]])", r"\1", text)  # komma's aan het eind (JSON5/JSONC)


def _xml_to_obj(el: ET.Element):
    tag = el.tag.split("}")[-1]
    children = list(el)
    node: dict = {f"@{k.split('}')[-1]}": v for k, v in el.attrib.items()}
    if children:
        for c in children:
            k, v = next(iter(_xml_to_obj(c).items()))
            if k in node:
                if not isinstance(node[k], list):
                    node[k] = [node[k]]
                node[k].append(v)
            else:
                node[k] = v
        if el.text and el.text.strip():
            node["#text"] = el.text.strip()
    else:
        text = (el.text or "").strip()
        if node:
            if text:
                node["#text"] = text
        else:
            node = text
    return {tag: node}


def _ini(text: str) -> dict:
    import configparser
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read_string(text if re.search(r"(?m)^\s*\[", text) else "[algemeen]\n" + text)
    except configparser.Error as e:
        raise ConversionError(f"Dit configuratiebestand kan niet gelezen worden: {e}") from e
    return {s: dict(cp.items(s)) for s in cp.sections()}


def _kv(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!", ";")):
            continue
        line = re.sub(r"^export\s+", "", line)
        m = re.match(r"([^=:]+?)\s*[=:]\s*(.*)", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip().strip('"').strip("'")
    return out


def load(path: Path):
    """Bestand -> Python-object (dict/list)."""
    from .textfmt import read_text
    ext = path.suffix.lower().lstrip(".")
    if ext in ("pkl", "pickle", "joblib"):
        raise ConversionError("Python-pickles worden niet geopend: ze kunnen code uitvoeren op je computer.")
    if ext == "plist":
        import plistlib
        return _plain(plistlib.loads(path.read_bytes()))
    if ext in ("npy", "npz"):
        import numpy as np
        arr = np.load(path, allow_pickle=False)
        if ext == "npz":
            return {k: arr[k].tolist() for k in arr.files}
        return arr.tolist()
    if ext == "msgpack":
        try:
            import msgpack
        except ImportError as e:
            raise ConversionError("MessagePack-ondersteuning ontbreekt.") from e
        return msgpack.unpackb(path.read_bytes(), raw=False)
    text = read_text(path)
    if ext in ("json", "jsonld", "webmanifest", "geojson", "har", "ipynb"):
        return json.loads(text)
    if ext in ("json5", "jsonc"):
        return json.loads(_strip_json_comments(text))
    if ext in ("jsonl", "ndjson"):
        return [json.loads(x) for x in text.splitlines() if x.strip()]
    if ext in ("yaml", "yml"):
        import yaml
        docs = list(yaml.safe_load_all(text))
        return docs[0] if len(docs) == 1 else docs
    if ext == "toml":
        import tomllib
        return tomllib.loads(text)
    if ext in ("xml", "xsd", "xsl", "xslt", "rss", "atom", "opml", "kml", "gpx"):
        return _xml_to_obj(ET.fromstring(text.encode("utf-8")))
    if ext in ("ini", "cfg", "conf"):
        try:
            return _ini(text)
        except ConversionError:
            return _kv(text)
    if ext in ("properties", "env"):
        return _kv(text)
    if ext in ("csv", "tsv"):
        dialect = "excel-tab" if ext == "tsv" else csv.Sniffer().sniff(text[:4096], ",;\t|") if text else "excel"
        return list(csv.DictReader(io.StringIO(text), dialect=dialect))
    try:
        return json.loads(text)
    except ValueError as e:
        raise ConversionError(f"Kan .{ext} niet als data lezen.") from e


def _plain(o):
    import datetime
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, bytes):
        return o.hex() if len(o) < 4096 else f"<{len(o)} bytes>"
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    return o


# --------------------------------------------------------------------------- schrijven

def table(obj) -> tuple[list[str], list[list]]:
    """Maak een tabel van (bijna) elke datastructuur: lijsten van objecten, dict met lijsten, enz."""
    rows = obj
    if isinstance(obj, dict):
        lists = [v for v in obj.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if len(lists) == 1:
            rows = lists[0]
        elif all(isinstance(v, dict) for v in obj.values()) and obj:
            rows = [{"sectie": k, **v} for k, v in obj.items()]
        else:
            rows = [{"sleutel": k, "waarde": v} for k, v in _flatten(obj).items()]
    if not isinstance(rows, list):
        rows = [rows]
    if rows and all(isinstance(r, list) for r in rows):
        width = max(len(r) for r in rows)
        return [f"kolom{i + 1}" for i in range(width)], [list(r) + [""] * (width - len(r)) for r in rows]
    flat = [_flatten(r) if isinstance(r, dict) else {"waarde": r} for r in rows]
    cols: list[str] = []
    for r in flat:
        for k in r:
            if k not in cols:
                cols.append(k)
    return cols, [[r.get(c, "") for c in cols] for r in flat]


def _flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)) and v and not (isinstance(v, list) and not isinstance(v[0], (dict, list))):
                out.update(_flatten(v, key))
            elif isinstance(v, list):
                out[key] = ", ".join(str(x) for x in v)
            else:
                out[key] = v
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix or "waarde"] = d
    return out


def _obj_xml(obj, tag="data") -> ET.Element:
    tag = re.sub(r"[^\w.-]", "_", str(tag)) or "item"
    if tag[0].isdigit():
        tag = "_" + tag
    el = ET.Element(tag)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("@") and not isinstance(v, (dict, list)):
                el.set(re.sub(r"[^\w.-]", "_", str(k)[1:]) or "attr", str(v))
            elif k == "#text":
                el.text = str(v)
            elif isinstance(v, list):
                for item in v:
                    el.append(_obj_xml(item, k))
            else:
                el.append(_obj_xml(v, k))
    elif isinstance(obj, list):
        for item in obj:
            el.append(_obj_xml(item, "item"))
    elif obj is not None:
        el.text = str(obj)
    return el


def _toml(obj) -> str:
    """Eenvoudige TOML-schrijver (tabellen, lijsten, tekst, getallen, booleans)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v if not isinstance(x, dict)) + "]"
        if v is None:
            return '""'
        return json.dumps(str(v), ensure_ascii=False)

    def emit(d, path, out):
        simple = {k: v for k, v in d.items() if not isinstance(v, dict) and
                  not (isinstance(v, list) and v and isinstance(v[0], dict))}
        if path and simple:
            out.append(f"\n[{'.'.join(path)}]")
        for k, v in simple.items():
            out.append(f"{json.dumps(str(k)) if not re.fullmatch(r'[A-Za-z0-9_-]+', str(k)) else k} = {val(v)}")
        for k, v in d.items():
            if isinstance(v, dict):
                emit(v, path + [str(k)], out)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for item in v:
                    out.append(f"\n[[{'.'.join(path + [str(k)])}]]")
                    for ik, iv in item.items():
                        if not isinstance(iv, dict):
                            out.append(f"{ik} = {val(iv)}")
    if not isinstance(obj, dict):
        obj = {"data": obj}
    out: list[str] = []
    emit(obj, [], out)
    return "\n".join(out).strip() + "\n"


def write(obj, dst: Path, fmt: str, title: str = "data") -> Path:
    import html as H
    if fmt in ("json", "json-mooi"):
        dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    elif fmt in ("yaml", "yaml-mooi"):
        import yaml
        dst.write_text(yaml.safe_dump(json.loads(json.dumps(obj, default=str)), allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
    elif fmt == "toml":
        dst.write_text(_toml(obj), encoding="utf-8")
    elif fmt in ("xml", "xml-mooi"):
        root = _obj_xml(obj if not (isinstance(obj, dict) and len(obj) == 1) else next(iter(obj.values())),
                        next(iter(obj)) if isinstance(obj, dict) and len(obj) == 1 else "data")
        ET.indent(root)
        dst.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n")
    elif fmt == "plist":
        import plistlib
        dst.write_bytes(plistlib.dumps(json.loads(json.dumps(obj, default=str)), fmt=plistlib.FMT_XML))
    elif fmt in ("csv", "tsv"):
        cols, rows = table(obj)
        with open(dst, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter="\t" if fmt == "tsv" else ",")
            w.writerow(cols)
            w.writerows(rows)
    elif fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = str(title)[:31] or "data"
        cols, rows = table(obj)
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append([v if isinstance(v, (int, float, bool)) or v is None else str(v)[:32000] for v in r])
        from .pdftools import _autowidth
        _autowidth(ws)
        wb.save(dst)
    elif fmt == "html":
        cols, rows = table(obj)
        body = "<tr>" + "".join(f"<th>{H.escape(str(c))}</th>" for c in cols) + "</tr>" + "".join(
            "<tr>" + "".join(f"<td>{H.escape(str(v))}</td>" for v in r) + "</tr>" for r in rows[:20000])
        dst.write_text(f"<!doctype html><meta charset='utf-8'><title>{H.escape(title)}</title><style>body{{font-family:"
                       f"sans-serif}}table{{border-collapse:collapse}}td,th{{border:1px solid #999;padding:3px 6px;"
                       f"font-size:13px}}th{{background:#eee}}</style><table>{body}</table>\n", encoding="utf-8")
    elif fmt == "txt":
        cols, rows = table(obj)
        widths = [min(40, max([len(str(c))] + [len(str(r[i])) for r in rows[:2000]])) for i, c in enumerate(cols)]
        lines = ["  ".join(str(c)[:40].ljust(widths[i]) for i, c in enumerate(cols)),
                 "  ".join("-" * w for w in widths)]
        lines += ["  ".join(str(v)[:40].ljust(widths[i]) for i, v in enumerate(r)) for r in rows]
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ConversionError(f"Data naar .{fmt} wordt niet ondersteund.")
    return dst


# --------------------------------------------------------------------------- databases

def sqlite_tables(path: Path) -> dict[str, tuple[list[str], list[tuple]]]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out = {}
        for (name,) in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            cur = con.execute(f'select * from "{name}"')
            out[name] = ([d[0] for d in cur.description], cur.fetchall())
        return out
    except sqlite3.DatabaseError as e:
        raise ConversionError(f"Dit is geen leesbare SQLite-database: {e}") from e
    finally:
        con.close()


def read_dbf(path: Path) -> tuple[list[str], list[list]]:
    data = path.read_bytes()
    if len(data) < 32:
        raise ConversionError("Ongeldig dBase-bestand.")
    n = int.from_bytes(data[4:8], "little")
    hlen = int.from_bytes(data[8:10], "little")
    rlen = int.from_bytes(data[10:12], "little")
    fields, pos = [], 32
    while pos < hlen - 1 and data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode("latin-1")
        fields.append((name, chr(data[pos + 11]), data[pos + 16]))
        pos += 32
    rows = []
    for i in range(n):
        rec = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        if not rec or rec[:1] == b"*":
            continue
        off, row = 1, []
        for name, typ, size in fields:
            raw = rec[off:off + size].decode("latin-1").strip()
            off += size
            if typ in "NF" and raw:
                try:
                    row.append(float(raw) if "." in raw else int(raw))
                except ValueError:
                    row.append(raw)
            elif typ == "L":
                row.append(raw.upper() in ("T", "Y"))
            elif typ == "D" and len(raw) == 8:
                row.append(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")
            else:
                row.append(raw)
        rows.append(row)
    return [f[0] for f in fields], rows


def convert_db(src: Path, out_dir: Path, fmt: str) -> Path:
    ext = src.suffix.lower().lstrip(".")
    tables = {"data": read_dbf(src)} if ext == "dbf" else sqlite_tables(src)
    if not tables:
        raise ConversionError("Deze database heeft geen tabellen.")
    stem = src.stem
    if fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        for name, (cols, rows) in tables.items():
            ws = wb.create_sheet(re.sub(r"[\[\]:*?/\\]", "_", name)[:31] or "tabel")
            ws.append(cols)
            for r in rows:
                ws.append([v if isinstance(v, (int, float, str)) or v is None else str(v) for v in r])
        dst = out_dir / f"{stem}.xlsx"
        wb.save(dst)
        return dst
    if fmt == "json":
        dst = out_dir / f"{stem}.json"
        dst.write_text(json.dumps({n: [dict(zip(c, r)) for r in rows] for n, (c, rows) in tables.items()},
                                  ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return dst
    if fmt == "sql":
        dst = out_dir / f"{stem}.sql"
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        dst.write_text("\n".join(con.iterdump()) + "\n", encoding="utf-8")
        con.close()
        return dst
    if fmt == "html":
        dst = out_dir / f"{stem}.html"
        parts = []
        for name, (cols, rows) in tables.items():
            tmp = out_dir / "_t.html"
            write([dict(zip(cols, r)) for r in rows], tmp, "html", name)
            parts.append(f"<h2>{name}</h2>" + re.search(r"<table>.*</table>", tmp.read_text(), re.S).group(0))
            tmp.unlink()
        dst.write_text("<!doctype html><meta charset='utf-8'><style>table{border-collapse:collapse}td,th{border:1px "
                       "solid #999;padding:3px 6px}</style>" + "".join(parts), encoding="utf-8")
        return dst
    if fmt == "csv":
        if len(tables) == 1:
            cols, rows = next(iter(tables.values()))
            dst = out_dir / f"{stem}.csv"
            with open(dst, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows([cols, *rows])
            return dst
        dst = out_dir / f"{stem}_tabellen.zip"
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for name, (cols, rows) in tables.items():
                buf = io.StringIO()
                csv.writer(buf).writerows([cols, *rows])
                z.writestr(f"{name}.csv", "﻿" + buf.getvalue())
        return dst
    raise ConversionError(f"Database naar .{fmt} wordt niet ondersteund.")


# --------------------------------------------------------------------------- speciale soorten

def notebook(src: Path, out_dir: Path, fmt: str) -> Path:
    nb = json.loads(src.read_text(encoding="utf-8"))
    lang = (nb.get("metadata", {}).get("kernelspec", {}) or {}).get("language", "python")
    md, py = [], []
    for cell in nb.get("cells", []):
        text = "".join(cell.get("source", []))
        if cell.get("cell_type") == "markdown":
            md.append(text)
            py.append("\n".join("# " + x for x in text.splitlines()))
        elif cell.get("cell_type") == "code":
            md.append(f"```{lang}\n{text}\n```")
            py.append(text)
            for o in cell.get("outputs", []):
                out = "".join(o.get("text", [])) or "".join(o.get("data", {}).get("text/plain", []))
                if out:
                    md.append("```\n" + out.rstrip() + "\n```")
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt == "py":
        dst.write_text("\n\n".join(py) + "\n", encoding="utf-8")
    elif fmt == "md":
        dst.write_text("\n\n".join(md) + "\n", encoding="utf-8")
    elif fmt == "txt":
        dst.write_text("\n\n".join(md) + "\n", encoding="utf-8")
    else:
        from .textfmt import markdown_html
        body = markdown_html("\n\n".join(md))
        if fmt == "html":
            dst.write_text(f"<!doctype html><meta charset='utf-8'><title>{src.stem}</title>{body}", encoding="utf-8")
        else:
            from .pdftools import html_to_pdf
            html_to_pdf(body, dst)
    return dst


def har_rows(src: Path) -> list[dict]:
    har = json.loads(src.read_text(encoding="utf-8"))
    rows = []
    for e in har.get("log", {}).get("entries", []):
        req, res = e.get("request", {}), e.get("response", {})
        rows.append({"tijd": e.get("startedDateTime"), "methode": req.get("method"), "url": req.get("url"),
                     "status": res.get("status"), "type": res.get("content", {}).get("mimeType"),
                     "grootte": res.get("content", {}).get("size"), "duur_ms": round(e.get("time", 0) or 0)})
    return rows


def feed_rows(src: Path) -> list[dict]:
    root = ET.fromstring(src.read_bytes())
    rows = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue

        def g(*names):
            for c in item:
                if c.tag.split("}")[-1] in names:
                    return c.get("href") or (c.text or "").strip()
            return ""
        rows.append({"titel": g("title"), "link": g("link"), "datum": g("pubDate", "updated", "published"),
                     "samenvatting": re.sub(r"<[^>]+>", "", g("description", "summary", "content"))[:500]})
    return rows


def opml_outline(src: Path) -> list[tuple[int, str, str]]:
    root = ET.fromstring(src.read_bytes())
    body = root.find("body")
    out = []

    def walk(el, depth):
        for o in el.findall("outline"):
            out.append((depth, o.get("text") or o.get("title") or "", o.get("xmlUrl") or o.get("url") or ""))
            walk(o, depth + 1)
    walk(body if body is not None else root, 0)
    return out


# --------------------------------------------------------------------------- bankbestanden

def finance_rows(src: Path) -> list[dict]:
    from .textfmt import read_text
    ext = src.suffix.lower().lstrip(".")
    text = read_text(src)
    rows = []
    if ext in ("ofx", "qfx", "qbo") or "<OFX>" in text.upper():
        for tx in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>)", text, re.S | re.I):
            def tag(t):
                m = re.search(rf"<{t}>([^<\r\n]*)", tx, re.I)
                return m.group(1).strip() if m else ""
            d = tag("DTPOSTED")
            rows.append({"datum": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else d, "bedrag": _num(tag("TRNAMT")),
                         "omschrijving": tag("NAME") or tag("MEMO"), "memo": tag("MEMO"), "type": tag("TRNTYPE"),
                         "id": tag("FITID")})
    elif ext == "qif" or text.startswith("!Type"):
        cur: dict = {}
        for line in text.splitlines():
            if not line:
                continue
            code, val = line[0], line[1:].strip()
            if code == "^":
                if cur:
                    rows.append(cur)
                cur = {}
            elif code == "D":
                cur["datum"] = val
            elif code in "TU":
                cur["bedrag"] = _num(val)
            elif code == "P":
                cur["omschrijving"] = val
            elif code == "M":
                cur["memo"] = val
            elif code == "L":
                cur["categorie"] = val
        if cur:
            rows.append(cur)
    elif ext in ("sta", "940") or ":61:" in text:
        lines = text.replace("\r", "").split("\n:")
        last = None
        for ln in lines:
            ln = ln.lstrip(":")
            if ln.startswith("61:"):
                m = re.match(r"61:(\d{6})(\d{4})?(R?[CD])([A-Z])?([\d,]+)", ln)
                if m:
                    d = m.group(1)
                    amount = _num(m.group(5))
                    last = {"datum": f"20{d[:2]}-{d[2:4]}-{d[4:]}", "bedrag": -amount if "D" in m.group(3) else amount,
                            "omschrijving": ""}
                    rows.append(last)
            elif ln.startswith("86:") and last is not None:
                last["omschrijving"] = " ".join(ln[3:].split())
    elif ext == "cod" or text.startswith("0000"):
        for line in text.splitlines():
            if line.startswith("21"):
                sign = -1 if line[31:32] == "1" else 1
                amount = int(line[32:47] or 0) / 1000 * sign
                d = line[47:53]
                rows.append({"datum": f"20{d[4:6]}-{d[2:4]}-{d[0:2]}", "bedrag": amount,
                             "omschrijving": line[62:115].strip()})
            elif line.startswith("22") and rows:
                rows[-1]["tegenpartij"] = line[10:63].strip()
            elif line.startswith("23") and rows:
                rows[-1]["rekening"] = line[10:47].strip()
    if not rows:
        raise ConversionError("Geen transacties gevonden in dit bankbestand.")
    return rows


def _num(s: str):
    s = (s or "").strip().replace(" ", "")
    if re.fullmatch(r"-?[\d.]*,\d+", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return s


# --------------------------------------------------------------------------- hoofdfunctie

def convert(src: Path, out_dir: Path, fmt: str, opts: dict) -> Path:
    ext = src.suffix.lower().lstrip(".")
    if ext in DB or (ext in ("db",) and src.read_bytes()[:15] == b"SQLite format 3"):
        return convert_db(src, out_dir, fmt)
    if ext == "ipynb":
        return notebook(src, out_dir, fmt)
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt.split('-')[0] == ext else ''}.{fmt.split('-')[0]}"
    if ext == "har":
        return write(har_rows(src), dst, fmt, src.stem)
    if ext in ("rss", "atom"):
        rows = feed_rows(src)
        if fmt == "md":
            dst.write_text("\n".join(f"- [{r['titel']}]({r['link']}) {r['datum']}" for r in rows) + "\n",
                           encoding="utf-8")
            return dst
        return write(rows, dst, fmt, src.stem)
    if ext == "opml":
        items = opml_outline(src)
        if fmt in ("md", "txt"):
            bullet = "- " if fmt == "md" else "* "
            dst.write_text("\n".join("  " * d + bullet + (f"[{t}]({u})" if u and fmt == "md" else t + (f" ({u})" if u
                                                                                                       else ""))
                                     for d, t, u in items) + "\n", encoding="utf-8")
            return dst
        return write([{"niveau": d, "tekst": t, "url": u} for d, t, u in items], dst, fmt, src.stem)
    if ext in FINANCE:
        return write(finance_rows(src), dst, fmt, src.stem)
    return write(load(src), dst, fmt, src.stem)
