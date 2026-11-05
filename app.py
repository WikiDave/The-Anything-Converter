"""The Anything Converter - webserver.

Start:  python app.py   en open http://localhost:8000
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from converter.detect import LABELS, TARGETS, detect, extension, media_info
from converter.jobs import JobManager
from converter import settings as user_settings
from converter import virus
from converter.util import ConversionError, parse_size

# In de desktop-app wijst CONVERTER_BASE naar de map met static/ (naast het programma).
BASE = Path(os.environ.get("CONVERTER_BASE") or Path(__file__).parent)
DESKTOP = os.environ.get("CONVERTER_DESKTOP") == "1"
def _read_version() -> str:
    exe = Path(sys.executable).resolve().parent
    # macOS-app: bestanden kunnen in Contents/MacOS of Contents/Resources staan
    for cand in (BASE / "VERSION", Path(__file__).parent / "VERSION", exe / "VERSION",
                 exe.parent / "Resources" / "VERSION"):
        try:
            return cand.read_text().strip()
        except OSError:
            pass
    return "0.0.0"


VERSION = _read_version()
WORK = Path(os.environ.get("CONVERTER_WORKDIR", Path(tempfile.gettempdir()) / "anything-converter"))
MAX_UPLOAD_MB = int(os.environ.get("CONVERTER_MAX_MB", "4096"))

app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
jobs = JobManager(WORK)
uploads: dict[str, dict] = {}


@app.get("/")
def index():
    return send_from_directory(BASE / "static", "index.html")


# De browser-versie (PDF- en archief-werkbank) wordt ook door de lokale/desktop-app aangeboden.
WEB_FILES = {"index.html", "favicon.svg", "favicon.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png",
             "manifest.webmanifest"}


@app.get("/web/")
def web_index():
    return send_from_directory(BASE, "index.html")


@app.get("/web/<path:name>")
def web_file(name):
    if name in WEB_FILES or name.startswith("vendor/"):
        return send_from_directory(BASE, name)
    abort(404)


@app.get("/api/ping")
def ping():
    """Laat de interface (en een tweede start van de desktop-app) weten dat de converter draait."""
    return jsonify(app="anything-converter", version=VERSION, desktop=DESKTOP, window=app.config.get("WINDOW"))


@app.post("/api/quit")
def quit_app():
    """Desktop-app afsluiten vanuit de interface."""
    stop = app.config.get("SHUTDOWN")
    if not DESKTOP or not stop:
        return jsonify(error="Alleen beschikbaar in de desktop-app."), 400
    import threading
    threading.Timer(0.3, stop).start()
    return jsonify(ok=True)


@app.post("/api/terminal")
def open_terminal():
    """Terminalversie openen in een nieuw terminalvenster (desktop-app)."""
    if not DESKTOP:
        return jsonify(error="Alleen beschikbaar in de desktop-app."), 400
    from converter.terminal import open_tui
    try:
        open_tui()
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)), 500
    return jsonify(ok=True)


@app.post("/api/upload")
def upload():
    """Eén bestand, of meerdere die bij elkaar horen (CUE + BIN's, ROM + patch)."""
    files = [f for f in request.files.getlist("file") if f and f.filename]
    if not files:
        return jsonify(error="Geen bestand ontvangen."), 400
    uid = uuid.uuid4().hex
    folder = WORK / uid
    folder.mkdir(parents=True)
    paths = []
    for f in files:
        name = safe_name(f.filename)
        path = folder / name
        n = 2
        while path.exists():
            path = folder / f"{Path(name).stem}_{n}{Path(name).suffix}"
            n += 1
        f.save(path)
        paths.append(path)
    return jsonify(register_upload(uid, pick_main(folder, paths)))


def safe_name(raw: str) -> str:
    """Bestandsnaam veilig maken maar herkenbaar houden (spaties, haakjes en accenten blijven;
    belangrijk voor ROM-namen en .cue-verwijzingen)."""
    import re
    import unicodedata
    name = unicodedata.normalize("NFC", raw.replace("\\", "/").rsplit("/", 1)[-1])
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip().lstrip(".")
    if not name or name in (".", ".."):
        name = secure_filename(raw) or "bestand"
    return name[:200]


def pick_main(folder: Path, paths: list[Path]) -> Path:
    """Welk bestand is 'het' bestand: de .cue bij BIN's, de ROM bij een patch, een zip met een schijf erin."""
    from converter import rom
    if len(paths) == 1 and paths[0].suffix.lower() in (".zip", ".7z"):
        inner = archive_listing(paths[0])
        if any(n.lower().endswith(tuple("." + e for e in rom.CUE_LIKE)) for n in inner):
            from converter.archive import _safe_extract
            _safe_extract(paths[0], folder)
            paths[0].unlink()
            paths = [p for p in folder.rglob("*") if p.is_file()]
    for ext in rom.CUE_LIKE:
        hit = next((p for p in paths if p.suffix.lower() == "." + ext), None)
        if hit:
            return hit
    rest = [p for p in paths if p.suffix.lower().lstrip(".") not in rom.PATCH_EXT]
    return rest[0] if rest else paths[0]


def archive_listing(path: Path) -> list[str]:
    import zipfile
    try:
        if zipfile.is_zipfile(path):
            return zipfile.ZipFile(path).namelist()
        import py7zr
        with py7zr.SevenZipFile(path) as z:
            return z.getnames()
    except Exception:  # noqa: BLE001
        return []


def register_upload(uid: str, path: Path) -> dict:
    """Maak een bestand beschikbaar voor conversie en geef de info voor de interface."""
    from converter import rom
    from converter.catalog import describe
    from converter.detect import targets_for
    patches = [p for p in path.parent.iterdir() if p.suffix.lower().lstrip(".") in rom.PATCH_EXT and p != path]
    category, eff, targets = targets_for(path, patches)
    info = media_info(path) if category in ("video", "audio", "image") and category != "rom" else {}
    desc = describe(path)
    if desc:
        info = dict(info, kind=desc)
    if eff and eff != extension(path):
        info = dict(info, real_ext=eff)
    if category in ("disc", "rom"):
        extra = [p.name for p in (rom.disc_files(path) if category == "disc" else [path, *patches])
                 if p != path]
        if extra:
            info = dict(info, files=extra)
    uploads[uid] = {"path": path, "category": category, "targets": targets}
    size = sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file()) if category == "disc" \
        else path.stat().st_size
    return dict(id=uid, name=path.name, size=size, ext=extension(path), category=category,
                label=LABELS.get(category, category), targets=targets, info=info)


@app.post("/api/fetch")
def fetch_url():
    """Video ophalen via een link (yt-dlp). Alleen voor eigen of vrij te gebruiken video's."""
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify(error="Plak eerst een link."), 400
    uid = uuid.uuid4().hex
    job = jobs.submit(WORK / uid, "fetch", {"url": url, "audio_only": bool(data.get("audio_only")),
                                            "scan": data.get("scan", True) is not False}, kind="fetch")
    job.extra["uid"] = uid
    return jsonify(job.public())


@app.post("/api/webshot")
def webshot_start():
    """Website opslaan als PDF/PNG/JPG (headless Chrome/Edge)."""
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get("url") or "").strip()
    fmt = str(data.get("format") or "pdf").lower()
    if not url or fmt not in ("pdf", "png", "jpg"):
        return jsonify(error="Geef een websiteadres en kies pdf, png of jpg."), 400
    job = jobs.submit(WORK / uuid.uuid4().hex, "webshot", {"url": url, "format": fmt}, kind="webshot")
    return jsonify(job.public())


@app.post("/api/hash/<uid>")
def file_hashes(uid):
    """Checksums van een geüpload bestand (optioneel HMAC met een sleutel)."""
    from converter.hashes import compute
    up = uploads.get(uid)
    if not up or not up["path"].exists():
        return jsonify(error="Bestand niet gevonden."), 404
    path = up["path"]
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(name=path.name, hashes=compute(path, str(data.get("key") or "") or None))


@app.post("/api/ocr/screen")
def ocr_screen():
    """Schermafbeelding maken (gebied kiezen) en de tekst herkennen. Alleen in de desktop-app/lokaal."""
    from converter import ocr
    try:
        shot = ocr.capture_screen()
        text = ocr.image(shot)
    except ConversionError as e:
        return jsonify(error=str(e)), 400
    return jsonify(text=text)


@app.post("/api/ocr/image")
def ocr_pasted():
    """Tekst herkennen in een geplakte/gesleepte afbeelding (klembord)."""
    from converter import ocr
    f = request.files.get("file")
    if not f:
        return jsonify(error="Geen afbeelding ontvangen."), 400
    try:
        text = ocr.image_bytes(f.read(), Path(f.filename or "x.png").suffix or ".png")
    except ConversionError as e:
        return jsonify(error=str(e)), 400
    return jsonify(text=text)


@app.get("/api/capabilities")
def capabilities():
    """Welke extra hulpprogramma's zijn er (voor uitleg in de interface)."""
    from converter import ebook, ocr, pdftools, webshot
    from converter.document import have
    from converter.unpack import sevenzip as sevenzip_tool
    speech_error = None
    try:
        import pywhispercpp.model  # noqa: F401
        speech = True
    except Exception as e:  # noqa: BLE001
        speech, speech_error = False, f"{type(e).__name__}: {e}"
    try:
        import py7zr  # noqa: F401
        sevenzip = True
    except Exception:  # noqa: BLE001
        sevenzip = False
    return jsonify(ocr=ocr.engine(), calibre=bool(ebook.calibre()), pymupdf=pdftools.have_pymupdf(),
                   speech=speech, speech_error=speech_error, sevenzip=sevenzip,
                   sevenzip_tool=bool(sevenzip_tool()),
                   libreoffice=have("soffice") or have("libreoffice"), chrome=bool(webshot.chromium()))


@app.post("/api/torrent")
def torrent_start():
    """Torrent downloaden: een .torrent-bestand (formulier) of een magnet-link (JSON)."""
    f = request.files.get("file")
    scan = request.values.get("scan", "1") != "0"
    if f and f.filename:
        source = f.read()
        if len(source) > 20 * 1024 * 1024:
            return jsonify(error="Dit .torrent-bestand is te groot."), 400
    else:
        data = request.get_json(force=True, silent=True) or {}
        source = str(data.get("magnet") or "").strip()
        scan = data.get("scan", True) is not False
        if not source.lower().startswith("magnet:?"):
            return jsonify(error="Plak een magnet-link (begint met magnet:?) of kies een .torrent-bestand."), 400
    uid = uuid.uuid4().hex
    job = jobs.submit(WORK / uid, "torrent", {"source": source, "scan": scan}, kind="torrent")
    job.extra["uid"] = uid
    return jsonify(job.public())


@app.post("/api/job/<job_id>/cancel")
def job_cancel(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Taak niet gevonden."), 404
    job.extra["cancel"] = True
    return jsonify(ok=True)


def _torrent_file(job_id: str, idx: int) -> Path:
    job = jobs.get(job_id)
    if not job or job.kind != "torrent" or job.status != "done":
        abort(404)
    if job.extra.get("virus", {}).get("status") == "infected":
        abort(403)
    files = {f["idx"]: f for f in job.extra.get("files", [])}
    if idx not in files:
        abort(404)
    root = job.result.resolve()
    path = (root / files[idx]["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        abort(404)
    return path


@app.get("/api/torrent/<job_id>/file/<int:idx>")
def torrent_file(job_id, idx):
    path = _torrent_file(job_id, idx)
    return send_file(path, as_attachment=True, download_name=path.name)


@app.post("/api/torrent/<job_id>/open/<int:idx>")
def torrent_open(job_id, idx):
    """Eén bestand uit de torrent in de converter openen."""
    path = _torrent_file(job_id, idx)
    return jsonify(register_upload(uuid.uuid4().hex, path))


@app.post("/api/job/<job_id>/delete")
def job_delete(job_id):
    """Download (bijv. met een virus) direct van de schijf verwijderen."""
    import shutil
    job = jobs.get(job_id)
    if not job or job.kind not in ("fetch", "torrent"):
        return jsonify(error="Taak niet gevonden."), 404
    target = job.src if job.src.is_dir() else job.src.parent
    if WORK.resolve() in target.resolve().parents:
        shutil.rmtree(target, ignore_errors=True)
    job.result = None
    job.extra["deleted"] = True
    return jsonify(ok=True)


@app.post("/api/scan/<uid>")
def scan_upload(uid):
    """Een geopend bestand op verzoek controleren op virussen."""
    up = uploads.get(uid)
    if not up or not up["path"].exists():
        return jsonify(error="Bestand niet gevonden."), 404
    return jsonify(virus.check(up["path"], user_settings.load().get("vt_key")))


@app.get("/api/settings")
def get_settings():
    s = user_settings.load()
    return jsonify(vt_key_set=bool(s.get("vt_key")), scanner=virus.available_engine())


@app.post("/api/settings")
def set_settings():
    data = request.get_json(force=True, silent=True) or {}
    s = user_settings.load()
    if "vt_key" in data:
        key = str(data["vt_key"] or "").strip()
        if key and (len(key) != 64 or not all(c in "0123456789abcdefABCDEF" for c in key)):
            return jsonify(error="Een VirusTotal-sleutel bestaat uit 64 tekens (0-9, a-f)."), 400
        s["vt_key"] = key
    user_settings.save(s)
    return jsonify(vt_key_set=bool(s.get("vt_key")))


@app.get("/api/file/<uid>")
def uploaded_file(uid):
    """Het geüploade/opgehaalde bestand zelf, voor de preview bij knippen."""
    up = uploads.get(uid)
    if not up or not up["path"].exists():
        abort(404)
    return send_file(up["path"], conditional=True, as_attachment=request.args.get("download") == "1",
                     download_name=up["path"].name)


@app.post("/api/convert")
def convert():
    data = request.get_json(force=True, silent=True) or {}
    up = uploads.get(data.get("id", ""))
    if not up or not up["path"].exists():
        return jsonify(error="Upload niet gevonden of verlopen. Upload het bestand opnieuw."), 404
    opts = {k: v for k, v in (data.get("options") or {}).items() if v not in (None, "", False)}
    try:
        if opts.get("target_size"):
            opts["target_bytes"] = parse_size(opts.pop("target_size"), opts.pop("target_unit", "mb"))
        opts.pop("target_unit", None)
    except ConversionError as exc:
        return jsonify(error=str(exc)), 400
    if opts.get("format") and opts["format"] not in up.get("targets", TARGETS.get(up["category"], [])):
        return jsonify(error=f"Formaat .{opts['format']} is niet mogelijk voor dit bestand."), 400
    job = jobs.submit(up["path"], up["category"], opts)
    return jsonify(job.public())


@app.get("/api/job/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Taak niet gevonden."), 404
    data = job.public()
    infected = job.extra.get("virus", {}).get("status") == "infected"
    if job.kind == "fetch" and job.status == "done" and job.result and not infected:
        if "upload" not in job.extra:
            job.extra["upload"] = register_upload(job.extra["uid"], job.result)
        data["upload"] = job.extra["upload"]
    return jsonify(data)


@app.get("/api/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job.status != "done" or not job.result or not job.result.exists():
        abort(404)
    return send_file(job.result, as_attachment=True, download_name=job.result.name)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error=f"Bestand is te groot (max {MAX_UPLOAD_MB} MB)."), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"The Anything Converter draait op http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}")
    app.run(host=host, port=port, threaded=True)
