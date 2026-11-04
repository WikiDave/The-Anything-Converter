"""The Anything Converter - webserver.

Start:  python app.py   en open http://localhost:8000
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from converter.detect import LABELS, TARGETS, detect, extension, media_info
from converter.jobs import JobManager
from converter.util import ConversionError, parse_size

# In de desktop-app wijst CONVERTER_BASE naar de map met static/ (naast het programma).
BASE = Path(os.environ.get("CONVERTER_BASE") or Path(__file__).parent)
DESKTOP = os.environ.get("CONVERTER_DESKTOP") == "1"
VERSION = "2.1.0"
WORK = Path(os.environ.get("CONVERTER_WORKDIR", Path(tempfile.gettempdir()) / "anything-converter"))
MAX_UPLOAD_MB = int(os.environ.get("CONVERTER_MAX_MB", "4096"))

app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
jobs = JobManager(WORK)
uploads: dict[str, dict] = {}


@app.get("/")
def index():
    return send_from_directory(BASE / "static", "index.html")


@app.get("/api/ping")
def ping():
    """Laat de interface (en een tweede start van de desktop-app) weten dat de converter draait."""
    return jsonify(app="anything-converter", version=VERSION, desktop=DESKTOP)


@app.post("/api/quit")
def quit_app():
    """Desktop-app afsluiten vanuit de interface."""
    stop = app.config.get("SHUTDOWN")
    if not DESKTOP or not stop:
        return jsonify(error="Alleen beschikbaar in de desktop-app."), 400
    import threading
    threading.Timer(0.3, stop).start()
    return jsonify(ok=True)


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Geen bestand ontvangen."), 400
    uid = uuid.uuid4().hex
    folder = WORK / uid
    folder.mkdir(parents=True)
    name = secure_filename(f.filename) or "bestand"
    if "." not in name and "." in f.filename:  # secure_filename kan niet-ASCII namen leegmaken
        name = "bestand." + f.filename.rsplit(".", 1)[-1].lower()
    path = folder / name
    f.save(path)
    return jsonify(register_upload(uid, path))


def register_upload(uid: str, path: Path) -> dict:
    """Maak een bestand beschikbaar voor conversie en geef de info voor de interface."""
    category = detect(path)
    info = media_info(path) if category in ("video", "audio", "image") else {}
    uploads[uid] = {"path": path, "category": category}
    return dict(id=uid, name=path.name, size=path.stat().st_size, ext=extension(path), category=category,
                label=LABELS[category], targets=TARGETS[category], info=info)


@app.post("/api/fetch")
def fetch_url():
    """Video ophalen via een link (yt-dlp). Alleen voor eigen of vrij te gebruiken video's."""
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify(error="Plak eerst een link."), 400
    uid = uuid.uuid4().hex
    job = jobs.submit(WORK / uid, "fetch", {"url": url, "audio_only": bool(data.get("audio_only"))}, kind="fetch")
    job.extra["uid"] = uid
    return jsonify(job.public())


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
    if opts.get("format") and opts["format"] not in TARGETS[up["category"]]:
        return jsonify(error=f"Formaat .{opts['format']} is niet mogelijk voor dit bestand."), 400
    job = jobs.submit(up["path"], up["category"], opts)
    return jsonify(job.public())


@app.get("/api/job/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Taak niet gevonden."), 404
    data = job.public()
    if job.kind == "fetch" and job.status == "done" and job.result:
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
