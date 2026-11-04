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

from . import archive, document, image, media
from .util import ConversionError


@dataclass
class Job:
    id: str
    src: Path
    category: str
    opts: dict
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    message: str = "In de wachtrij"
    result: Optional[Path] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)

    def public(self) -> dict:
        d = {"id": self.id, "status": self.status, "progress": round(self.progress, 3), "message": self.message}
        if self.result:
            d.update(filename=self.result.name, size=self.result.stat().st_size,
                     original_size=self.src.stat().st_size)
        if self.error:
            d["error"] = self.error
        return d


def run_conversion(src: Path, out_dir: Path, category: str, opts: dict, progress=None) -> Path:
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

    def submit(self, src: Path, category: str, opts: dict) -> Job:
        job = Job(id=uuid.uuid4().hex, src=src, category=category, opts=opts)
        with self.lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def _run(self, job: Job) -> None:
        with self.sem:
            job.status, job.message = "running", "Starten"
            out_dir = job.src.parent / f"out_{job.id[:8]}"
            out_dir.mkdir(exist_ok=True)

            def progress(frac: float, msg: str) -> None:
                job.progress, job.message = max(job.progress, min(frac, 0.99)), msg

            try:
                job.result = run_conversion(job.src, out_dir, job.category, job.opts, progress)
                job.status, job.progress, job.message = "done", 1.0, "Klaar"
            except ConversionError as exc:
                job.status, job.error, job.message = "error", str(exc), "Mislukt"
            except Exception as exc:  # onverwacht: log voor debugging
                traceback.print_exc()
                job.status, job.error, job.message = "error", f"Onverwachte fout: {exc}", "Mislukt"

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
