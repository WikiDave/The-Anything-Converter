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

BASE = Path(__file__).parent
WORK = Path(os.environ.get("CONVERTER_WORKDIR", Path(tempfile.gettempdir()) / "anything-converter"))
MAX_UPLOAD_MB = int(os.environ.get("CONVERTER_MAX_MB", "4096"))

app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
jobs = JobManager(WORK)
uploads: dict[str, dict] = {}


@app.get("/")
def index():
    return send_from_directory(BASE / "static", "index.html")


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
    category = detect(path)
    info = media_info(path) if category in ("video", "audio", "image") else {}
    ext = extension(path)
    uploads[uid] = {"path": path, "category": category}
    return jsonify(id=uid, name=name, size=path.stat().st_size, ext=ext, category=category,
                   label=LABELS[category], targets=TARGETS[category], info=info)


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
    return jsonify(job.public())


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
