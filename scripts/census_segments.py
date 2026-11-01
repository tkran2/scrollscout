"""check-segment on every published segment that can be checked.

Lists every ``<scroll>/segments/<id>/`` folder in the open-data bucket, keeps those with a tifxyz mesh
traced on a volume that has a published surface prediction, and runs ``check-segment`` on each (12
points). Writes ``results/segment_census.json`` (resumable) and ``census/SEGMENTS.md`` + ``census/segments.csv``.

    SCROLLSCOUT_NO_CACHE=1 python -I scripts/census_segments.py --calibration results/calibration.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrollscout.catalog import Catalog, list_prefixes  # noqa: E402
from scrollscout.scout import Calibration, validated_scan  # noqa: E402
from scrollscout.segment import FOLLOWS, check_segment, infer_volume, load_surface  # noqa: E402

BUCKET = "s3://vesuvius-challenge-open-data"


def checkable(cat: Catalog) -> tuple[list[dict], list[dict]]:
    """Every published segment with a tifxyz mesh on a volume that has a surface prediction, split into
    those on the scan types the score was validated on (8.6-9.4 um) and the rest."""
    jobs = [(s, seg) for s in cat.scrolls() for seg in list_prefixes(f"{s}/segments/")]

    def probe(job):
        scroll, seg = job
        tif = [m for m in list_prefixes(seg + "mesh/") if m.rstrip("/").endswith(".tifxyz")]
        m = re.search(r"-on-(\d{14})", tif[0]) if tif else None
        if not m:
            return None
        try:
            vol = cat.volume(scroll, m.group(1))
        except KeyError:
            return None
        if vol.surface is None:
            return None
        return {"scroll": scroll, "segment": seg.rstrip("/").split("/")[-1], "volume": vol.volume,
                "voxel_um": vol.voxel_um, "validated": validated_scan(vol), "url": f"{BUCKET}/{seg}"}

    with ThreadPoolExecutor(16) as ex:
        found = sorted((r for r in ex.map(probe, jobs) if r), key=lambda r: (r["scroll"], r["segment"]))
    return [r for r in found if r["validated"]], [r for r in found if not r["validated"]]


def survey_labels(path: Path) -> dict:
    if not path.exists():
        return {}
    segs = json.loads(path.read_text()).get("published_segments", [])
    return {(s["scroll"], s["segment"]): s["visual_qa"]["surface"] for s in segs}


def write_tables(rows: list[dict], out_dir: Path, skipped: list[dict] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["scroll", "segment", "volume", "verdict", "median_score", "frac_clean", "n_points", "no_papyrus",
            "area_cm2", "survey_verdict", "url"]
    with open(out_dir / "segments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "no_papyrus": len(r["no_papyrus"])})
    by_scroll: dict[str, list[dict]] = {}
    for r in rows:
        by_scroll.setdefault(r["scroll"], []).append(r)
    ok = [r for r in rows if np.isfinite(r["median_score"])]
    n_follow = sum(r["verdict"] == FOLLOWS for r in ok)
    skipped = skipped or []
    skip_note = []
    if skipped:
        per = {}
        for r in skipped:
            per.setdefault((r["scroll"], r["voxel_um"]), 0)
            per[(r["scroll"], r["voxel_um"])] += 1
        skip_note = ["", "Not checked: " + ", ".join(f"{n} segments of {s} ({um:g} µm scan)" for (s, um), n in per.items())
                     + ", because the score was validated on 8.64 µm and 9.36 µm scans only."]
    lines = ["# Every published segment, checked",
             "",
             f"`scrollscout check-segment` on all {len(rows)} segments in the open-data bucket that have a tifxyz",
             "mesh traced on an 8.6–9.4 µm scan with a published surface prediction (12 points each). "
             f"{n_follow} of {len(ok)} likely follow their sheet.",
             *skip_note,
             "",
             "A segment *likely follows the sheet* when its median point scores above the clean threshold (0.63).",
             "This rule called all 20 of the team's segments that the First Letters survey judged by eye correctly;",
             "on other scrolls it is a prediction, not a measurement. *No papyrus* counts points whose",
             "surroundings show no papyrus in the CT (the segment leaves the scroll or the scan there).",
             "",
             "| scroll | segments | likely follow the sheet | likely cut across layers |",
             "|---|---:|---:|---:|"]
    for s, rs in sorted(by_scroll.items()):
        f_ = sum(r["verdict"] == FOLLOWS for r in rs if np.isfinite(r["median_score"]))
        n_ = sum(np.isfinite(r["median_score"]) for r in rs)
        lines.append(f"| {s} | {len(rs)} | {f_} | {n_ - f_} |")
    for s, rs in sorted(by_scroll.items()):
        lines += ["", f"## {s}", "",
                  "| segment | verdict | median score | points clean | no papyrus | survey (by eye) |",
                  "|---|---|---:|---:|---:|---|"]
        for r in sorted(rs, key=lambda r: -np.nan_to_num(r["median_score"], nan=-9)):
            sv = (r.get("survey_verdict") or "").split(";")[0].split(".")[0][:60]
            v = r["verdict"].replace("likely ", "")
            med = f"{r['median_score']:+.2f}" if np.isfinite(r["median_score"]) else "–"
            fc = f"{r['frac_clean']:.0%}" if np.isfinite(r["frac_clean"]) else "–"
            lines.append(f"| `{r['segment']}` | {v} | {med} | {fc} | {len(r['no_papyrus'])} | {sv} |")
    (out_dir / "SEGMENTS.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--index")
    ap.add_argument("--survey", default=str(ROOT / "data" / "first_letters_survey_results.json"))
    ap.add_argument("--points", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "results" / "segment_census.json"))
    ap.add_argument("--tables", default=str(ROOT / "census"))
    ap.add_argument("--limit", type=int, help="check only the first N segments (for a quick try)")
    a = ap.parse_args()
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    out = Path(a.out)
    done = {r["url"]: r for r in json.loads(out.read_text())["segments"]} if out.exists() else {}
    labels = survey_labels(Path(a.survey))
    todo, skipped = checkable(cat)
    todo = todo[: a.limit]
    print(f"{len(todo)} checkable segments ({len(done)} already done); {len(skipped)} on unvalidated scans skipped",
          flush=True)
    rows = []
    for i, j in enumerate(todo, 1):
        if j["url"] in done:
            rows.append(done[j["url"]])
            continue
        try:
            surf = load_surface(j["url"])
            vol = infer_volume(surf, cat, j["scroll"], j["volume"])
            res = check_segment(surf, vol, cal, a.points, a.workers)
        except Exception as e:  # keep going: one broken mesh should not stop the census
            print(f"[{i}/{len(todo)}] {j['scroll']} {j['segment']}: failed ({e!r})", flush=True)
            continue
        s = res["summary"]
        rows.append({**j, "n_nodes": s["n_nodes"], "area_cm2": s["area_cm2"], "n_points": s["n_points"],
                     "median_score": s["median_score"], "frac_clean": s["frac_clean"], "verdict": s["verdict"],
                     "no_papyrus": s["no_papyrus"], "trouble_spots": s["trouble_spots"],
                     "survey_verdict": labels.get((j["scroll"], j["segment"])), "points": res["points"]})
        print(f"[{i}/{len(todo)}] {j['scroll']} {j['segment'][:40]:<40} {s['median_score']:+.2f} -> {s['verdict']}",
              flush=True)
        out.write_text(json.dumps({"segments": rows}, indent=1, default=float))
    skipped = [{k: r[k] for k in ("scroll", "segment", "volume", "voxel_um", "url")} for r in skipped]
    out.write_text(json.dumps({"segments": rows, "skipped": skipped}, indent=1, default=float))
    write_tables(rows, Path(a.tables), skipped)
    ok = [r for r in rows if np.isfinite(r["median_score"])]
    print(f"\n{sum(r['verdict'] == FOLLOWS for r in ok)} of {len(ok)} segments likely follow their sheet; "
          f"tables in {a.tables}")


if __name__ == "__main__":
    main()
