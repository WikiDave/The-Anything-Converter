"""Bestanden controleren op virussen.

Gebruikt de scanner die al op de computer staat:
- Windows: Microsoft Defender (MpCmdRun.exe), standaard aanwezig.
- macOS / Linux: ClamAV (clamdscan of clamscan), als die geïnstalleerd is.
Daarnaast altijd een SHA-256-vingerafdruk met een VirusTotal-link; met een (gratis) VirusTotal-API-sleutel
wordt die vingerafdruk ook automatisch opgezocht. Het bestand zelf wordt nooit geüpload.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .util import NO_WINDOW

VT_GUI = "https://www.virustotal.com/gui/file/"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _defender() -> Optional[str]:
    if os.name != "nt":
        return None
    cands = sorted(glob.glob(os.path.expandvars(r"%ProgramData%\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe")),
                   reverse=True)
    cands.append(os.path.expandvars(r"%ProgramFiles%\Windows Defender\MpCmdRun.exe"))
    return next((c for c in cands if os.path.isfile(c)), None)


def available_engine() -> Optional[str]:
    if _defender():
        return "Microsoft Defender"
    if shutil.which("clamdscan") or shutil.which("clamscan"):
        return "ClamAV"
    return None


def _run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, **NO_WINDOW)


def scan_local(path: Path) -> dict:
    """Scan een bestand of map met de lokale scanner. status: clean | infected | unknown."""
    exe = _defender()
    if exe:
        try:
            p = _run([exe, "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"])
        except Exception as exc:
            return {"engine": "Microsoft Defender", "status": "unknown", "detail": f"scan failed: {exc}"}
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            return {"engine": "Microsoft Defender", "status": "clean", "detail": "no threats found"}
        if p.returncode == 2 or "threat" in out.lower():
            names = [ln.split(":", 1)[-1].strip() for ln in out.splitlines() if "Threat" in ln and ":" in ln]
            return {"engine": "Microsoft Defender", "status": "infected",
                    "detail": ", ".join(names[:5]) or "threat found"}
        return {"engine": "Microsoft Defender", "status": "unknown", "detail": out.strip()[-300:] or f"code {p.returncode}"}

    clam = shutil.which("clamdscan") or shutil.which("clamscan")
    if clam:
        cmd = [clam, "--no-summary", "--infected"]
        if path.is_dir():
            cmd.append("-r" if clam.endswith("clamscan") else "--multiscan")
        cmd.append(str(path))
        try:
            p = _run(cmd)
        except Exception as exc:
            return {"engine": "ClamAV", "status": "unknown", "detail": f"scan failed: {exc}"}
        if p.returncode == 0:
            return {"engine": "ClamAV", "status": "clean", "detail": "no viruses found"}
        if p.returncode == 1:
            found = [ln.rsplit(":", 1)[-1].replace("FOUND", "").strip() for ln in p.stdout.splitlines() if "FOUND" in ln]
            return {"engine": "ClamAV", "status": "infected", "detail": ", ".join(found[:5]) or "virus found"}
        return {"engine": "ClamAV", "status": "unknown", "detail": (p.stderr or p.stdout).strip()[-300:]}

    hint = ("install ClamAV (macOS: brew install clamav · Linux: sudo apt install clamav) or use the VirusTotal check")
    return {"engine": None, "status": "unknown", "detail": "no virus scanner found on this computer: " + hint}


def virustotal(digest: str, api_key: Optional[str]) -> Optional[dict]:
    """Zoek alleen de vingerafdruk op bij VirusTotal (het bestand wordt niet geüpload)."""
    if not api_key:
        return None
    req = urllib.request.Request(f"https://www.virustotal.com/api/v3/files/{digest}", headers={"x-apikey": api_key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            stats = json.load(r)["data"]["attributes"]["last_analysis_stats"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "unknown", "detail": "never seen by VirusTotal"}
        if exc.code in (401, 403):
            return {"status": "unknown", "detail": "VirusTotal key is wrong"}
        return {"status": "unknown", "detail": f"VirusTotal returned error {exc.code}"}
    except Exception as exc:
        return {"status": "unknown", "detail": f"VirusTotal not reachable ({exc.__class__.__name__})"}
    bad = stats.get("malicious", 0) + stats.get("suspicious", 0)
    total = sum(stats.values())
    return {"status": "infected" if stats.get("malicious", 0) else "clean",
            "detail": f"{bad} of {total} scanners report something"}


def check(path: Path, api_key: Optional[str] = None) -> dict:
    """Volledige controle van een bestand of map. Resultaat voor de interface."""
    files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
    local = scan_local(path)
    hashes = []
    for f in files[:200]:  # bij enorme torrents niet alles hashen
        try:
            d = sha256(f)
        except OSError:
            continue
        entry = {"name": f.name, "sha256": d, "virustotal": VT_GUI + d}
        vt = virustotal(d, api_key) if len(files) <= 4 else None  # gratis sleutel: max 4 opvragingen per minuut
        if vt:
            entry["vt"] = vt
        hashes.append(entry)
    infected = local["status"] == "infected" or any(h.get("vt", {}).get("status") == "infected" for h in hashes)
    clean = local["status"] == "clean" and not infected
    return {"status": "infected" if infected else "clean" if clean else "unknown", "local": local, "files": hashes}
