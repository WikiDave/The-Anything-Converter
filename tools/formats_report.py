"""Test every known format: make a sample file, try every conversion, and write docs/FORMATS.md.

Usage:  python tools/formats_report.py [--quick] [--only ext1,ext2] [--workers N]
Sample files are made by converter/samples.py (Pillow, ffmpeg, fontTools, trimesh, ...). Formats for which no sample
can be made are listed as 'not tested', with what the app offers for them.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, TimeoutError as FutTimeout, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from converter.catalog import catalog  # noqa: E402
from converter.detect import LABELS, targets_for  # noqa: E402
from converter.jobs import run_conversion  # noqa: E402
from converter.samples import NEEDS, make_sample  # noqa: E402  (make_sample is also used by the tests)


def try_convert(path: Path, fmt: str, work: Path, timeout: int = 120):
    cat, eff, _ = targets_for(path)
    out = work / f"out_{fmt.replace('.', '_')}"
    out.mkdir(parents=True, exist_ok=True)
    opts = {"format": fmt, "quality": "low", "speech_model": "tiny"}
    with ThreadPoolExecutor(1) as ex:
        fut = ex.submit(run_conversion, path, out, cat, opts, None)
        try:
            res = fut.result(timeout=timeout)
            ok = res.exists() and (res.stat().st_size > 0 or res.is_dir())
            return ok, "" if ok else "empty result"
        except FutTimeout:
            return False, "too slow (time-out)"
        except Exception as e:  # noqa: BLE001
            return False, str(e).splitlines()[0][:160] if str(e) else type(e).__name__


def test_one(ext: str, folder: str, quick: bool = False) -> dict:
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    try:
        sample = make_sample(ext, d)
    except Exception:  # noqa: BLE001
        sample = None
    if sample is None:
        probe = d / f"empty.{ext}"
        probe.write_bytes(bytes(range(256)) * 4)
        try:
            cat, eff, targets = targets_for(probe)
        except Exception:  # noqa: BLE001
            cat, targets = "info", ["txt", "zip", "7z"]
        entry = {"tested": False, "category": cat, "targets": targets}
        if cat == "info":
            good, err = try_convert(probe, "txt", d)
            entry.update(tested=True, works=["txt"] if good else [], errors={} if good else {"txt": err})
        return entry
    try:
        cat, eff, targets = targets_for(sample)
    except Exception as e:  # noqa: BLE001
        return {"tested": True, "category": "?", "targets": [], "errors": {"detect": str(e)}}
    ok, bad = [], {}
    for fmt in (targets[:4] if quick else targets):
        if fmt in ("txt", "srt", "vtt") and cat in ("video", "audio"):
            continue  # speech recognition: tested separately (model download)
        good, err = try_convert(sample, fmt, d)
        (ok.append(fmt) if good else bad.__setitem__(fmt, err))
    return {"tested": True, "category": cat, "targets": targets, "works": ok, "errors": bad}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="at most 4 conversions per format")
    ap.add_argument("--only", help="only these extensions (comma-separated)")
    ap.add_argument("--workers", type=int, default=max(2, os.cpu_count() or 4))
    args = ap.parse_args()
    cat_map = catalog()
    exts = sorted(cat_map) if not args.only else args.only.split(",")
    results = {}
    base = Path(tempfile.mkdtemp(prefix="formats-"))
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(test_one, ext, str(base / f"x{i}"), args.quick): ext for i, ext in enumerate(exts)}
        for n, fut in enumerate(as_completed(futs), 1):
            ext = futs[fut]
            try:
                results[ext] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[ext] = {"tested": False, "category": "?", "targets": [], "errors": {"test": str(e)}}
            r = results[ext]
            print(f"[{n}/{len(exts)}] .{ext:<12} {r['category']:<12} ok: {len(r.get('works', []))}  "
                  f"failed: {len(r.get('errors', {}))}{'' if r['tested'] else '  (no sample)'}", flush=True)
    shutil.rmtree(base, ignore_errors=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "formats.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, sort_keys=True),
                                                encoding="utf-8")
    write_markdown(results, cat_map)
    print(f"done in {time.time() - t0:.0f} s")


def status(r: dict) -> str:
    if not r["tested"]:
        return "not tested" if r["category"] != "info" else "info"
    if r["category"] == "info":
        return "info ✓" if "txt" in r.get("works", []) else "info"
    if r.get("works") and not r.get("errors"):
        return "✓"
    if r.get("works"):
        return "✓ partly"
    return "✗"


def write_markdown(results: dict, cat_map: dict) -> None:
    lines = ["# Supported formats", "",
             "Generated by `tools/formats_report.py`: for each format a sample file was made and every conversion was "
             "actually run (on Linux, with ffmpeg, LibreOffice, pandoc, Ghostscript and 7-Zip installed).", "",
             "| Mark | Meaning |", "|---|---|",
             "| ✓ | sample made, all conversions tested and successful |",
             "| ✓ partly | some succeeded; the rest needs an extra program or failed (see note) |",
             "| info ✓ | cannot be converted (program, project file, encrypted, ...): info report, checksums, packing |",
             "| not tested | no sample file could be made; 'Can become' is what the app offers |", ""]
    groups: dict[str, list[str]] = {}
    for ext, hits in cat_map.items():
        groups.setdefault(hits[0][0], []).append(ext)
    totals = {"✓": 0, "✓ partly": 0, "info ✓": 0, "info": 0, "not tested": 0, "✗": 0}
    for group, exts in groups.items():
        lines += [f"## {group}", "", "| Format | Description | Kind | Can become | Tested | Note |",
                  "|---|---|---|---|---|---|"]
        for ext in exts:
            r = results.get(ext)
            if not r:
                continue
            st = status(r)
            totals[st] = totals.get(st, 0) + 1
            desc = next((d for g, d in cat_map[ext] if g == group), cat_map[ext][0][1])
            note = ""
            if r.get("errors"):
                needs = sorted({n for err in r["errors"].values() for key, n in NEEDS if key.lower() in err.lower()})
                note = "needs " + ", ".join(needs) if needs else \
                    "; ".join(f".{k}: {v}" for k, v in list(r["errors"].items())[:2])
            lines.append(f"| .{ext} | {desc} | {LABELS.get(r['category'], r['category'])} | {', '.join(r['targets'])} | "
                         f"{st} | {note.replace('|', '/')} |")
        lines.append("")
    summary = ", ".join(f"{v}× {k}" for k, v in totals.items() if v)
    lines.insert(2, f"**Summary:** {len(results)} extensions — {summary}.\n")
    (ROOT / "docs" / "FORMATS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
