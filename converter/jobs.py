"""Eenvoudige achtergrond-jobs met voortgang en automatische opruiming."""
from __future__ import annotations

import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import archive, document, fetch, image, media, ocr, settings, torrent, transcribe, virus
from .util import ConversionError


@dataclass
class Job:
    id: str
    src: Path
    category: str
    opts: dict
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    message: str = "Queued"
    result: Optional[Path] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)
    kind: str = "convert"  # convert | fetch | torrent
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        d = {"id": self.id, "status": self.status, "progress": round(self.progress, 3), "message": self.message}
        if self.result and self.kind == "torrent":
            d.update(name=self.extra.get("name"), files=self.extra.get("files", []))
        elif self.result:
            d.update(filename=self.result.name, size=self.result.stat().st_size)
            if self.src.is_file():
                d["original_size"] = (sum(p.stat().st_size for p in self.src.parent.iterdir() if p.is_file())
                                      if self.category == "disc" else self.src.stat().st_size)
        if self.error:
            d["error"] = self.error
        if "virus" in self.extra:
            d["virus"] = self.extra["virus"]
        return d


def run_conversion(src: Path, out_dir: Path, category: str, opts: dict, progress=None) -> Path:
    from . import families
    from .detect import analyse_path, extension
    fmt = (opts.get("format") or "").lower()
    real_cat, eff = analyse_path(src)
    if category in families.FAMILY_LABELS or real_cat in families.FAMILY_LABELS:
        return families.process(src, out_dir, real_cat if real_cat in families.FAMILY_LABELS else category, eff, opts,
                                progress)
    if eff and eff != extension(src):  # bijv. film.mp4.crdownload: behandelen als .mp4
        src = families.with_ext(src, eff, out_dir / "_in")
    if category == "spreadsheet" and eff in ("csv", "tsv") and fmt in ("json", "yaml", "xml", "txt", "toml", "html"):
        from . import datafmt
        return datafmt.convert(src, out_dir, fmt, opts)
    if category in ("video", "audio") and fmt in transcribe.TEXT_FORMATS:
        from .util import parse_time
        start = parse_time(opts.get("trim_start")) or 0.0
        end = parse_time(opts.get("trim_end"))
        return transcribe.transcribe(src, out_dir / f"{src.stem}.{fmt}", fmt, opts, progress, start, end)
    if category == "image" and fmt in ("txt", "docx", "rtf", "xlsx"):
        if progress:
            progress(0.2, "recognising text (OCR)")
        text = ocr.image(src)
        if not text.strip():
            raise ConversionError("No text was found in this image.")
        if progress:
            progress(0.9, "saving")
        from .pdftools import text_to_document
        return text_to_document(text, out_dir / f"{src.stem}.{fmt}", fmt)
    if category in ("disc", "rom"):
        from . import rom
        return rom.process(src, out_dir, category, opts, progress)
    if category == "ebook" or (category == "document" and fmt in ("mobi", "azw3", "fb2", "epub")):
        from . import ebook
        return ebook.convert(src, out_dir, fmt, opts, progress)
    if category == "presentation" and fmt in ("png", "jpg"):
        # eerst naar PDF, dan elke dia als afbeelding
        pdf = document.process(src, out_dir, category, dict(opts, format="pdf"), progress)
        from .pdftools import convert_pdf
        return convert_pdf(pdf, out_dir, fmt, opts, progress)
    if category in ("video", "audio"):
        return media.process(src, out_dir, opts, progress)
    if category == "image":
        return image.process(src, out_dir, opts, progress)
    if category in ("pdf", "document", "spreadsheet", "presentation"):
        return document.process(src, out_dir, category, opts, progress)
    return archive.process(src, out_dir, opts, progress)


class JobManager:
    def __init__(self, root: Path, max_age: int = 3600, workers: int = 2):
        self.root = root
        self.max_age = max_age
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.sem = threading.Semaphore(workers)
        root.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def submit(self, src: Path, category: str, opts: dict, kind: str = "convert") -> Job:
        job = Job(id=uuid.uuid4().hex, src=src, category=category, opts=opts, kind=kind)
        with self.lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def _run(self, job: Job) -> None:
        with self.sem:
            job.status, job.message = "running", "Starten"
            # fetch: src is de (lege) uploadmap waar de download in komt
            out_dir = job.src if job.kind in ("fetch", "torrent") else job.src.parent / f"out_{job.id[:8]}"
            out_dir.mkdir(parents=True, exist_ok=True)

            def progress(frac: float, msg: str) -> None:
                job.progress, job.message = max(job.progress, min(frac, 0.99)), msg

            try:
                if job.kind == "torrent":
                    res = torrent.download(job.opts["source"], out_dir, progress,
                                           cancelled=lambda: job.extra.get("cancel", False))
                    job.extra.update(name=res["name"], files=res["files"])
                    job.result = res["root"]
                    self._scan(job, res["root"], progress)
                elif job.kind == "webshot":
                    from . import webshot
                    job.result = webshot.capture(job.opts["url"], out_dir, job.opts["format"], progress)
                elif job.kind == "fetch":
                    job.result = fetch.download(job.opts["url"], out_dir, bool(job.opts.get("audio_only")), progress)
                    self._scan(job, job.result, progress)
                else:
                    opts = dict(job.opts, _cancelled=lambda: job.extra.get("cancel", False))
                    job.result = run_conversion(job.src, out_dir, job.category, opts, progress)
                job.status, job.progress, job.message = "done", 1.0, "Done"
            except ConversionError as exc:
                job.status, job.error, job.message = "error", str(exc), "Failed"
            except Exception as exc:  # onverwacht: log voor debugging
                traceback.print_exc()
                job.status, job.error, job.message = "error", f"Unexpected error: {exc}", "Failed"

    @staticmethod
    def _scan(job: Job, path: Path, progress) -> None:
        """Download automatisch op virussen controleren (tenzij uitgezet)."""
        if not job.opts.get("scan", True):
            return
        progress(0.995, "Check for viruses")
        job.extra["virus"] = virus.check(path, settings.load().get("vt_key"))
        if job.extra["virus"]["status"] == "infected":
            job.message = "Virus found"

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(300)
            now = time.time()
            for d in self.root.iterdir():
                try:
                    if now - d.stat().st_mtime > self.max_age:
                        shutil.rmtree(d, ignore_errors=True)
                except FileNotFoundError:
                    pass
            with self.lock:
                for jid in [j for j, job in self.jobs.items() if now - job.created > self.max_age]:
                    del self.jobs[jid]
