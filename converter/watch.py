"""Watch folders: every new file in a folder is converted with a preset, into an output folder.

- A file is only taken once it has stopped growing (downloads and copies in progress are left alone).
- What has been done is remembered per folder (name, size, time), also after a restart: nothing twice.
- The original is never changed; results go to the output folder (default: <folder>/converted), with the same
  subfolders, and an existing file is never overwritten.
Used by the desktop app (settings: 'watch') and by 'anything-converter-tui watch' (foreground, also over SSH/Docker).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from . import presets, settings
from .util import ConversionError

SKIP_SUFFIX = {".part", ".partial", ".crdownload", ".download", ".tmp", ".temp", ".!ut", ".!qb", ".swp", ".lock"}
SKIP_PREFIX = (".", "~$", "._")


class Watcher:
    def __init__(self, rules: list[dict] | None = None, state_file: Path | None = None, interval: float = 3.0,
                 on_event=None):
        self.rules = rules  # None = read from the settings (desktop app)
        self.state_file = state_file or settings._path().with_name("watch_done.json")
        self.interval = interval
        self.on_event = on_event
        self.log: deque = deque(maxlen=200)
        self.busy: str = ""
        self._seen: dict[str, tuple] = {}      # path -> (size, mtime) at the previous scan
        self._done = self._load_done()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ rules (desktop app: in the settings)
    def get_rules(self) -> list[dict]:
        if self.rules is not None:
            return self.rules
        return settings.load().get("watch", [])

    @staticmethod
    def add_rule(folder: str, preset: str, out: str = "", recursive: bool = True, existing: bool = False) -> dict:
        src = Path(folder).expanduser()
        if not src.is_dir():
            raise ValueError(f"Folder not found: {folder}")
        preset = presets.resolve(preset)  # KeyError if unknown
        dst = Path(out).expanduser() if out else src / "converted"
        if dst.resolve() == src.resolve():
            raise ValueError("The output folder must differ from the watched folder.")
        rule = {"id": uuid.uuid4().hex[:10], "folder": str(src.resolve()), "preset": preset, "out": str(dst),
                "recursive": bool(recursive), "existing": bool(existing), "enabled": True, "since": time.time()}
        s = settings.load()
        s.setdefault("watch", []).append(rule)
        settings.save(s)
        return rule

    @staticmethod
    def update_rule(rule_id: str, **changes) -> None:
        s = settings.load()
        for r in s.get("watch", []):
            if r["id"] == rule_id:
                r.update({k: v for k, v in changes.items() if k in ("enabled",)})
        settings.save(s)

    @staticmethod
    def remove_rule(rule_id: str) -> None:
        s = settings.load()
        s["watch"] = [r for r in s.get("watch", []) if r["id"] != rule_id]
        settings.save(s)

    # ------------------------------------------------------------------ state
    def _load_done(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_done(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(self._done), encoding="utf-8")
        except OSError:
            pass

    def _event(self, kind: str, rule: dict, name: str, text: str) -> None:
        e = {"time": time.strftime("%H:%M:%S"), "kind": kind, "rule": rule.get("id"), "file": name, "text": text}
        self.log.appendleft(e)
        if self.on_event:
            self.on_event(e)

    # ------------------------------------------------------------------ scanning
    def _candidates(self, rule: dict):
        root = Path(rule["folder"])
        out = Path(rule["out"]).resolve()
        it = root.rglob("*") if rule.get("recursive", True) else root.glob("*")
        for p in it:
            try:
                if not p.is_file() or p.name.startswith(SKIP_PREFIX) or p.suffix.lower() in SKIP_SUFFIX:
                    continue
                if out in p.resolve().parents:
                    continue  # our own results
            except OSError:
                continue
            yield p

    def scan_once(self) -> int:
        """One pass over all enabled rules; returns how many files were converted."""
        n = 0
        for rule in self.get_rules():
            if not rule.get("enabled", True) or not Path(rule["folder"]).is_dir():
                continue
            done = self._done.setdefault(rule["id"], {})
            for p in list(self._candidates(rule)):
                if self._stop.is_set():
                    return n
                try:
                    st = p.stat()
                except OSError:
                    continue
                key, sig = str(p), (st.st_size, int(st.st_mtime))
                rel = str(p.relative_to(rule["folder"]))
                if done.get(rel) == f"{sig[0]}:{sig[1]}":
                    continue
                # only files that existed before the rule started? no: everything new since then, and older
                # files only when the rule says so (default: start with what is there now)
                if self._seen.get(key) != sig or time.time() - st.st_mtime < 2:
                    self._seen[key] = sig      # still growing, or just appeared: next scan
                    continue
                if st.st_mtime < rule.get("since", 0) and not rule.get("existing", False):
                    done[rel] = f"{sig[0]}:{sig[1]}"   # was already there when the folder was added
                    continue
                n += self._convert(rule, p, rel)
                done[rel] = f"{sig[0]}:{sig[1]}"
                self._save_done()
        return n

    def _convert(self, rule: dict, src: Path, rel: str) -> int:
        from .detect import targets_for
        from .jobs import run_conversion
        try:
            preset = presets.get(rule["preset"])
        except KeyError:
            self._event("error", rule, rel, f"preset '{rule['preset']}' no longer exists")
            return 0
        opts = dict(preset["opts"])
        try:
            cat, eff, targets = targets_for(src)
        except Exception as e:  # noqa: BLE001
            self._event("skip", rule, rel, f"not recognised ({e})")
            return 0
        if preset.get("for") and cat not in preset["for"] or opts["format"] not in targets:
            self._event("skip", rule, rel, f"{cat} file: '{rule['preset']}' does not apply")
            return 0
        self.busy = rel
        work = Path(tempfile.mkdtemp(prefix="watch-"))
        try:
            self._event("start", rule, rel, f"converting to .{opts['format']}")
            res = run_conversion(src, work, cat, opts, None)
            dest_dir = Path(rule["out"]) / Path(rel).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / res.name
            i = 2
            while dest.exists():
                dest = dest_dir / f"{res.stem}_{i}{res.suffix}"
                i += 1
            shutil.move(str(res), dest)
            self._event("done", rule, rel, f"-> {dest}")
            return 1
        except ConversionError as e:
            self._event("error", rule, rel, str(e))
        except Exception as e:  # noqa: BLE001
            self._event("error", rule, rel, f"unexpected error: {e}")
        finally:
            self.busy = ""
            shutil.rmtree(work, ignore_errors=True)
        return 0

    # ------------------------------------------------------------------ background thread
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="watch-folders")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception as e:  # noqa: BLE001 - keep watching
                print("watch folders:", e)
            self._stop.wait(self.interval)

    def status(self) -> dict:
        rules = []
        for r in self.get_rules():
            done = self._done.get(r["id"], {})
            rules.append(dict(r, files_seen=len(done), exists=Path(r["folder"]).is_dir()))
        return {"rules": rules, "busy": self.busy, "log": list(self.log)[:60]}
