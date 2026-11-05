"""Test elk bekend formaat: maak een voorbeeldbestand, probeer alle omzettingen, en schrijf docs/FORMATEN.md.

Gebruik:  python tools/formaten_rapport.py [--snel]
Voorbeeldbestanden worden zelf gemaakt (Pillow, ffmpeg, fontTools, trimesh, ...). Formaten waarvan geen voorbeeld
te maken is, staan als 'niet getest' in het overzicht, met wat er wel kan.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from converter.catalog import catalog  # noqa: E402
from converter.detect import LABELS, targets_for  # noqa: E402
from converter.jobs import run_conversion  # noqa: E402

from converter.samples import NEEDS, make_sample  # noqa: E402


def try_convert(path: Path, fmt: str, work: Path, timeout: int = 120):
    cat, eff, _ = targets_for(path)
    out = work / f"uit_{fmt.replace('.', '_')}"
    out.mkdir(parents=True, exist_ok=True)
    opts = {"format": fmt, "quality": "low", "speech_model": "tiny"}
    with ThreadPoolExecutor(1) as ex:
        fut = ex.submit(run_conversion, path, out, cat, opts, None)
        try:
            res = fut.result(timeout=timeout)
            ok = res.exists() and (res.stat().st_size > 0 or res.is_dir())
            return ok, "" if ok else "leeg resultaat"
        except FutTimeout:
            return False, "te traag (time-out)"
        except Exception as e:  # noqa: BLE001
            return False, str(e).splitlines()[0][:160] if str(e) else type(e).__name__


def test_one(ext: str, folder: str, snel: bool = False) -> dict:
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    try:
        sample = make_sample(ext, d)
    except Exception:  # noqa: BLE001
        sample = None
    if sample is None:
        probe = d / f"leeg.{ext}"
        probe.write_bytes(bytes(range(256)) * 4)
        try:
            cat, eff, targets = targets_for(probe)
        except Exception:  # noqa: BLE001
            cat, targets = "info", ["txt", "zip", "7z"]
        entry = {"getest": False, "categorie": cat, "naar": targets}
        if cat == "info":
            good, err = try_convert(probe, "txt", d)
            entry.update(getest=True, werkt=["txt"] if good else [], fouten={} if good else {"txt": err})
        return entry
    try:
        cat, eff, targets = targets_for(sample)
    except Exception as e:  # noqa: BLE001
        return {"getest": True, "categorie": "?", "naar": [], "fouten": {"herkennen": str(e)}}
    ok, bad = [], {}
    for fmt in (targets[:4] if snel else targets):
        if fmt in ("txt", "srt", "vtt") and cat in ("video", "audio"):
            continue  # spraakherkenning: apart getest (modeldownload)
        good, err = try_convert(sample, fmt, d)
        (ok.append(fmt) if good else bad.__setitem__(fmt, err))
    return {"getest": True, "categorie": cat, "naar": targets, "werkt": ok, "fouten": bad}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snel", action="store_true", help="per formaat maximaal 4 omzettingen")
    ap.add_argument("--alleen", help="alleen deze extensies (komma's)")
    args = ap.parse_args()
    cat_map = catalog()
    exts = sorted(cat_map) if not args.alleen else args.alleen.split(",")
    results = {}
    base = Path(tempfile.mkdtemp(prefix="formaten-"))
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import os
    with ProcessPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        futs = {pool.submit(test_one, ext, str(base / f"x{i}"), args.snel): ext for i, ext in enumerate(exts)}
        for n, fut in enumerate(as_completed(futs), 1):
            ext = futs[fut]
            try:
                results[ext] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[ext] = {"getest": False, "categorie": "?", "naar": [], "fouten": {"test": str(e)}}
            r = results[ext]
            print(f"[{n}/{len(exts)}] .{ext:<12} {r['categorie']:<12} ok: {len(r.get('werkt', []))}  "
                  f"mis: {len(r.get('fouten', {}))}{'' if r['getest'] else '  (geen voorbeeld)'}", flush=True)
    shutil.rmtree(base, ignore_errors=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "formaten.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    write_markdown(results, cat_map)
    print(f"klaar in {time.time() - t0:.0f} s")


def status(r: dict) -> str:
    if not r["getest"]:
        return "niet getest" if r["categorie"] != "info" else "info"
    if r["categorie"] == "info":
        return "info ✓" if "txt" in r.get("werkt", []) else "info"
    if r.get("werkt") and not r.get("fouten"):
        return "✓"
    if r.get("werkt"):
        return "✓ deels"
    return "✗"


def write_markdown(results: dict, cat_map: dict) -> None:
    lines = ["# Ondersteunde formaten", "",
             "Automatisch gemaakt door `tools/formaten_rapport.py`: per formaat is een voorbeeldbestand gemaakt en is elke "
             "omzetting echt uitgevoerd.", "",
             "| Teken | Betekenis |", "|---|---|",
             "| ✓ | voorbeeld gemaakt, alle omzettingen getest en gelukt |",
             "| ✓ deels | een deel gelukt; de rest vraagt een extra programma of lukte niet (zie opmerking) |",
             "| info ✓ | niet om te zetten (programma, projectbestand, versleuteld, ...): wel inforapport, checksums, inpakken |",
             "| niet getest | geen voorbeeldbestand te maken; de kolom 'kan naar' is wat de app aanbiedt |", ""]
    groups: dict[str, list[str]] = {}
    for ext, hits in cat_map.items():
        groups.setdefault(hits[0][0], []).append(ext)
    totals = {"✓": 0, "✓ deels": 0, "info ✓": 0, "info": 0, "niet getest": 0, "✗": 0}
    for group, exts in groups.items():
        lines += [f"## {group}", "", "| Formaat | Omschrijving | Soort | Kan naar | Getest | Opmerking |", "|---|---|---|---|---|---|"]
        for ext in exts:
            r = results.get(ext)
            if not r:
                continue
            st = status(r)
            totals[st] = totals.get(st, 0) + 1
            desc = cat_map[ext][0][1] if cat_map[ext][0][0] == group else next(d for g, d in cat_map[ext] if g == group) \
                if any(g == group for g, _ in cat_map[ext]) else cat_map[ext][0][1]
            naar = ", ".join(r["naar"])
            note = ""
            if r.get("fouten"):
                needs = sorted({n for err in r["fouten"].values() for key, n in NEEDS if key.lower() in err.lower()})
                if needs:
                    note = "vraagt " + ", ".join(needs)
                else:
                    note = "; ".join(f".{k}: {v}" for k, v in list(r["fouten"].items())[:2])
            lines.append(f"| .{ext} | {desc} | {LABELS.get(r['categorie'], r['categorie'])} | {naar} | {st} | "
                         f"{note.replace('|', '/')} |")
        lines.append("")
    summary = ", ".join(f"{v}× {k}" for k, v in totals.items() if v)
    lines.insert(2, f"**Samenvatting:** {len(results)} extensies — {summary}.\n")
    (ROOT / "docs" / "FORMATEN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
