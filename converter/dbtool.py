"""Mini-databasetester: SQLite-bestanden, .sql-dumps en CSV/TSV/Excel bekijken en bevragen.

Werkt altijd op een kopie (werk.sqlite naast de upload); het originele bestand verandert nooit.
ATTACH en het laden van extensies zijn uitgeschakeld, zodat een query niet bij andere bestanden kan.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import sqlite3
from pathlib import Path

from .util import ConversionError

MAX_ROWS = 500
SQL_DUMP = {"sql", "dump"}
SQLITE = {"sqlite", "sqlite3", "db", "db3"}
TABULAR = {"csv", "tsv", "xlsx", "xlsm", "ods", "dbf", "json", "jsonl", "ndjson"}


def can_open(path: Path) -> bool:
    ext = path.suffix.lower().lstrip(".")
    if ext in SQL_DUMP | TABULAR:
        return True
    try:
        return path.read_bytes()[:15] == b"SQLite format 3"
    except OSError:
        return False


def work_path(src: Path) -> Path:
    return src.parent / "_werk.sqlite"


def _authorizer(action, arg1, arg2, dbname, source):
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def connect(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db), timeout=10)
    con.set_authorizer(_authorizer)
    return con


def _table_name(stem: str) -> str:
    name = re.sub(r"\W+", "_", stem).strip("_") or "table"
    return name if not name[0].isdigit() else "t_" + name


def prepare(src: Path | None, folder: Path) -> Path:
    """Maak (of hergebruik) de werkkopie. Zonder bron: een lege database."""
    db = folder / "_werk.sqlite"
    if db.exists():
        return db
    if src is None:
        sqlite3.connect(db).close()
        return db
    ext = src.suffix.lower().lstrip(".")
    if src.read_bytes()[:15] == b"SQLite format 3":
        shutil.copyfile(src, db)
        return db
    con = connect(db)
    try:
        if ext in SQL_DUMP:
            from .textfmt import read_text
            script = read_text(src)
            try:
                con.executescript(script)
            except sqlite3.Error as e:
                con.close()
                db.unlink(missing_ok=True)
                raise ConversionError(f"This SQL cannot be loaded into SQLite: {e}. (MySQL/PostgreSQL dumps with their own commands do not always work.)") from e
        else:
            _import_table(con, src)
        con.commit()
    finally:
        con.close()
    return db


def _import_table(con: sqlite3.Connection, src: Path) -> None:
    ext = src.suffix.lower().lstrip(".")
    sheets: list[tuple[str, list[str], list[list]]] = []
    if ext in ("xlsx", "xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(src, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            rows = [r for r in rows if any(v is not None for v in r)]
            if rows:
                sheets.append((ws.title, [str(c) if c is not None else f"column{i + 1}" for i, c in enumerate(rows[0])],
                               rows[1:]))
    elif ext == "dbf":
        from .datafmt import read_dbf
        cols, rows = read_dbf(src)
        sheets.append((src.stem, cols, rows))
    elif ext in ("json", "jsonl", "ndjson", "ods"):
        from .datafmt import load, table
        if ext == "ods":
            raise ConversionError("Convert an .ods file to .xlsx or .csv first.")
        cols, rows = table(load(src))
        sheets.append((src.stem, cols, rows))
    else:
        from .textfmt import read_text
        text = read_text(src)
        dialect = "excel-tab" if ext == "tsv" else csv.Sniffer().sniff(text[:4096], ",;\t|")
        rows = list(csv.reader(io.StringIO(text), dialect))
        if not rows:
            raise ConversionError("This file is empty.")
        sheets.append((src.stem, rows[0], rows[1:]))
    for name, cols, rows in sheets:
        cols = [re.sub(r"\s+", " ", str(c)).strip() or f"column{i + 1}" for i, c in enumerate(cols)]
        seen: dict[str, int] = {}
        for i, c in enumerate(cols):  # dubbele kolomnamen uniek maken
            if c.lower() in seen:
                seen[c.lower()] += 1
                cols[i] = f"{c}_{seen[c.lower()]}"
            else:
                seen[c.lower()] = 1
        tname = _table_name(name)
        con.execute(f'CREATE TABLE "{tname}" ({", ".join(chr(34) + c.replace(chr(34), "") + chr(34) for c in cols)})')
        width = len(cols)
        if ext in ("csv", "tsv"):  # getallen als getallen, zodat vergelijken en sorteren klopt
            from .pdftools import _cell
            rows = [[_cell(v) if v not in ("", None) else None for v in r] for r in rows]
        con.executemany(f'INSERT INTO "{tname}" VALUES ({", ".join("?" * width)})',
                        [(list(r) + [None] * width)[:width] for r in rows])


def overview(db: Path) -> list[dict]:
    con = connect(db)
    try:
        out = []
        for name, kind, sql in con.execute("select name, type, sql from sqlite_master where type in ('table','view') "
                                           "and name not like 'sqlite_%' order by type, name"):
            count = con.execute(f'select count(*) from "{name}"').fetchone()[0]
            cols = [{"naam": r[1], "type": r[2] or "", "sleutel": bool(r[5])}
                    for r in con.execute(f'pragma table_info("{name}")')]
            out.append({"naam": name, "soort": "tabel" if kind == "table" else "view", "rijen": count,
                        "kolommen": cols, "sql": sql or ""})
        return out
    finally:
        con.close()


def _clean(v):
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    if isinstance(v, str) and len(v) > 2000:
        return v[:2000] + "…"
    return v


def rows(db: Path, table: str, offset: int = 0, limit: int = 200) -> dict:
    con = connect(db)
    try:
        names = {r[0] for r in con.execute("select name from sqlite_master where type in ('table','view')")}
        if table not in names:
            raise ConversionError("Table does not exist.")
        cur = con.execute(f'select * from "{table}" limit ? offset ?', (min(limit, MAX_ROWS), max(0, offset)))
        total = con.execute(f'select count(*) from "{table}"').fetchone()[0]
        return {"kolommen": [d[0] for d in cur.description], "rijen": [[_clean(v) for v in r] for r in cur.fetchall()],
                "totaal": total, "vanaf": offset}
    finally:
        con.close()


def query(db: Path, sql: str) -> dict:
    """Voer SQL uit. Meerdere opdrachten mogen; het resultaat van de laatste SELECT wordt getoond."""
    sql = (sql or "").strip()
    if not sql:
        raise ConversionError("Type an SQL statement first.")
    if re.search(r"\b(attach|detach)\b", sql, re.I) or "load_extension" in sql.lower():
        raise ConversionError("ATTACH and loading extensions are disabled here.")
    con = connect(db)
    try:
        statements = [s for s in _split(sql) if s.strip()]
        result = {"kolommen": [], "rijen": [], "gewijzigd": 0, "meer": False}
        for st in statements:
            cur = con.execute(st)
            if cur.description:
                data = cur.fetchmany(MAX_ROWS + 1)
                result = {"kolommen": [d[0] for d in cur.description],
                          "rijen": [[_clean(v) for v in r] for r in data[:MAX_ROWS]], "gewijzigd": 0,
                          "meer": len(data) > MAX_ROWS}
            else:
                result["gewijzigd"] += max(cur.rowcount, 0)
        con.commit()
        result["opdrachten"] = len(statements)
        return result
    except sqlite3.Error as e:
        con.rollback()
        raise ConversionError(f"SQL error: {e}") from e
    finally:
        con.close()


def _split(sql: str) -> list[str]:
    """Opdrachten splitsen op ';' buiten tekst, met sqlite3.complete_statement als controle."""
    out, cur = [], ""
    for part in sql.split(";"):
        cur += part + ";"
        if sqlite3.complete_statement(cur):
            out.append(cur.strip().rstrip(";").strip())
            cur = ""
    if cur.strip(" ;\n\t"):
        out.append(cur.strip().rstrip(";"))
    return out


def export(db: Path, fmt: str, out_dir: Path, name: str, sql: str | None = None) -> Path:
    """De hele database (sqlite, sql, xlsx, json, html) of één queryresultaat (csv/xlsx)."""
    stem = re.sub(r"[^\w.-]+", "_", Path(name).stem) or "database"
    if sql:
        res = query(db, sql)
        from .datafmt import write
        return write([dict(zip(res["kolommen"], r)) for r in res["rijen"]], out_dir / f"{stem}_result.{fmt}", fmt,
                     "result")
    if fmt == "sqlite":
        dst = out_dir / f"{stem}.sqlite"
        src = connect(db)
        dest = sqlite3.connect(dst)
        src.backup(dest)
        dest.close()
        src.close()
        return dst
    from .datafmt import convert_db
    tmp = out_dir / f"{stem}.sqlite"
    shutil.copyfile(db, tmp)
    out = convert_db(tmp, out_dir, fmt)
    if out != tmp:
        tmp.unlink(missing_ok=True)
    return out


# --------------------------------------------------------------------------- teksteditor

EDITABLE_MAX = 5 * 1024 * 1024


def can_edit(path: Path, category: str) -> bool:
    size = path.stat().st_size
    if size > EDITABLE_MAX:
        return False
    if size == 0:
        return True  # nieuw/leeg bestand
    if category in ("text", "data", "subtitle", "playlist", "contact", "calendar", "cert", "gps", "vector") and \
            path.suffix.lower() not in (".ai", ".xps", ".oxps", ".eps", ".ps", ".der", ".kmz", ".fit", ".svgz"):
        from .catalog import looks_text
        return looks_text(path.read_bytes()[:8192])
    if category in ("document", "spreadsheet") and path.suffix.lower() in (".txt", ".csv", ".tsv", ".md", ".rst",
                                                                          ".tex", ".html", ".htm"):
        return True
    return False


def validate(text: str, ext: str) -> str | None:
    """Controleer bekende opmaak; geeft een foutmelding (met regelnummer) of None."""
    try:
        if ext in ("json", "jsonld", "webmanifest", "geojson", "ipynb", "har"):
            import json
            json.loads(text)
        elif ext in ("yaml", "yml"):
            import yaml
            list(yaml.safe_load_all(text))
        elif ext == "toml":
            import tomllib
            tomllib.loads(text)
        elif ext in ("xml", "svg", "gpx", "kml", "xsd", "xsl", "xslt", "plist", "ttml", "dfxp", "xspf", "rss", "atom",
                     "opml", "csproj", "vbproj", "fsproj", "vcxproj", "props", "targets", "xaml", "resx", "pom"):
            from xml.etree import ElementTree as ET
            ET.fromstring(text.encode("utf-8"))
        elif ext in ("jsonl", "ndjson"):
            import json
            for n, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    try:
                        json.loads(line)
                    except ValueError as e:
                        return f"line {n}: {e}"
    except Exception as e:  # noqa: BLE001
        return str(e).splitlines()[0][:300]
    return None
