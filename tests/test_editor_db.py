"""Teksteditor en databasetester: server-API, terminal-opdracht en veiligheid."""
import io
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import app as server
from converter import dbtool
from converter.util import ConversionError

ROOT = Path(__file__).resolve().parent.parent


def upload(name: str, data: bytes) -> dict:
    return server.app.test_client().post("/api/upload", data={"file": (io.BytesIO(data), name)}).get_json()


def test_edit_and_validate_json():
    c = server.app.test_client()
    up = upload("data.json", b'{"a": 1}')
    assert up["info"]["edit"] is True
    assert c.get(f"/api/text/{up['id']}").get_json()["text"] == '{"a": 1}'
    bad = c.post(f"/api/text/{up['id']}", json={"text": '{"a": 1,}', "check": True}).get_json()
    assert bad["ok"] is False and bad["error"]
    saved = c.post(f"/api/text/{up['id']}", json={"text": '{"a": 2}'}).get_json()
    assert saved["ok"] and server.uploads[up["id"]]["path"].read_text() == '{"a": 2}'
    # daarna gewoon omzetten met de bewerkte inhoud
    job = c.post("/api/convert", json={"id": up["id"], "options": {"format": "yaml"}}).get_json()
    assert "id" in job


def test_new_text_and_binary_not_editable():
    c = server.app.test_client()
    new = c.post("/api/text/new", json={"name": "notities.md"}).get_json()
    assert new["name"] == "notities.md" and new["info"]["edit"] is True
    png = upload("x.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
    assert png["info"].get("edit") is False


def test_database_tester_flow():
    c = server.app.test_client()
    db = c.post("/api/db/new").get_json()
    assert db["info"]["db"] is True
    uid = db["id"]
    assert c.post(f"/api/db/{uid}/open").get_json()["tables"] == []
    r = c.post(f"/api/db/{uid}/query", json={"sql": "CREATE TABLE t (a INT, b TEXT); INSERT INTO t VALUES (1,'x'),(2,'y');"
                                                     " SELECT * FROM t ORDER BY a DESC"}).get_json()
    assert r["result"]["rijen"] == [[2, "y"], [1, "x"]] and r["tables"][0]["rijen"] == 2
    assert c.get(f"/api/db/{uid}/table?name=t").get_json()["totaal"] == 2
    err = c.post(f"/api/db/{uid}/query", json={"sql": "SELECT * FROM nope"}).get_json()
    assert "SQL error" in err["error"]
    for fmt in ("sqlite", "sql", "xlsx", "csv", "json"):
        res = c.get(f"/api/db/{uid}/export?fmt={fmt}")
        assert res.status_code == 200 and len(res.data) > 10, fmt
    res = c.get(f"/api/db/{uid}/export?fmt=csv&sql=SELECT%20b%20FROM%20t")
    assert b"b" in res.data and b"y" in res.data


def test_sql_dump_and_csv_open(tmp_path):
    dump = tmp_path / "dump.sql"
    dump.write_text("CREATE TABLE p (naam TEXT); INSERT INTO p VALUES ('Anna');")
    (tmp_path / "w1").mkdir()
    db = dbtool.prepare(dump, tmp_path / "w1")
    assert dbtool.overview(db)[0]["naam"] == "p"
    csv_file = tmp_path / "mensen.csv"
    csv_file.write_text("naam;leeftijd\nAnna;30\nBo;25\n")
    (tmp_path / "w2").mkdir()
    db2 = dbtool.prepare(csv_file, tmp_path / "w2")
    assert dbtool.rows(db2, "mensen")["totaal"] == 2


def test_attach_is_blocked(tmp_path):
    (tmp_path / "w").mkdir()
    db = dbtool.prepare(None, tmp_path / "w")
    other = tmp_path / "geheim.sqlite"
    sqlite3.connect(other).execute("create table x(a)").connection.commit()
    with pytest.raises(ConversionError):
        dbtool.query(db, f"ATTACH DATABASE '{other}' AS g")
    with pytest.raises(ConversionError):
        dbtool.query(db, "SELECT load_extension('x')")


def test_sql_command_line(tmp_path):
    csv_file = tmp_path / "m.csv"
    csv_file.write_text("naam,leeftijd\nAnna,30\nBo,25\n")
    tui = [sys.executable, "-W", "ignore", str(ROOT / "tui.py")]
    r = subprocess.run([*tui, "sql", str(csv_file)], capture_output=True, text=True)
    assert "table m (2 rows)" in r.stdout
    r = subprocess.run([*tui, "sql", str(csv_file), "SELECT naam FROM m WHERE leeftijd > 26"], capture_output=True, text=True)
    assert "Anna" in r.stdout and "Bo" not in r.stdout
