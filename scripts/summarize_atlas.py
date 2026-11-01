"""Turn atlas/*.json into atlas/SUMMARY.md (ranked table) and atlas/seeds.csv (every recommended seed).

Two seed lists per scroll:
* ``best``: the highest-scoring sample points anywhere in the scroll;
* ``inner``: the highest-scoring points within 0.45 of the way from the axis to the outside, where both
  known text finds on the 116 keV protocol (PHerc. 343, PHerc. 1447) lie, and away from the top and
  bottom 15% of the scroll, where a roll's blank margins are.

    python -I scripts/summarize_atlas.py atlas
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.atlas import INNER_R as INNER  # noqa: E402
from scrollscout.atlas import inner_seeds  # noqa: E402


def main(atlas_dir: str, dense_dir: str = "atlas_dense"):
    d = Path(atlas_dir)
    items = [json.loads(f.read_text()) for f in sorted(d.glob("PHerc*.json"))]
    items.sort(key=lambda r: -r["summary"]["score_p90"])
    # rankings come from the even atlas pass; seeds come from the denser scan where one exists
    for it in items:
        f = Path(dense_dir) / f"{it['summary']['scroll']}.json"
        if f.exists():
            dense = json.loads(f.read_text())
            it["seed_points"], it["seed_summary"] = dense["points"], dense["summary"]
        else:
            it["seed_points"], it["seed_summary"] = it["points"], it["summary"]
    lines = [
        "# Scroll Scout atlas: First Letters eligible volumes",
        "",
        "Ranked by the score of each scroll's best 10% of sample points (higher = cleaner, easier-to-trace papyrus).",
        "Seeds are level-0 voxel coordinates (x, y, z) of the eligible volume, for VC3D *Create Segment (GrowPatch)*",
        f"or `fls.py run --seed X Y Z`. 'Inner' seeds lie within {INNER} of the way from the axis to the outside, where",
        "both known text finds on the 116 keV protocol (PHerc. 343, PHerc. 1447) are, and away from the top and bottom",
        "15% of the scroll (a roll's blank margins).",
        "",
        "| rank | scroll | scan | points | median | best 10% | share clean | best seed (x, y, z) | score | best inner seed (x, y, z) | score |",
        "|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|",
    ]
    rows = []
    for i, it in enumerate(items, 1):
        s = it["summary"]
        scan = f"{s['voxel_um']:.2f} µm / {s['energy_kev']:.0f} keV"
        best = it["seed_summary"]["seeds"][0] if it["seed_summary"]["seeds"] else None
        inn = inner_seeds(it["seed_points"])
        b = inn[0] if inn else None
        fmt = lambda sd: f"{sd['zyx'][2]}, {sd['zyx'][1]}, {sd['zyx'][0]}" if sd else "-"  # noqa: E731
        lines.append(f"| {i} | {s['scroll']} | {scan} | {s['n_points']} | {s['score_median']:.2f} | {s['score_p90']:.2f} | "
                     f"{s['frac_clean']:.0%} | {fmt(best)} | {best['score']:.2f} | {fmt(b)} | "
                     f"{(b['score'] if b else float('nan')):.2f} |")
        for zone, seeds in (("best", it["seed_summary"]["seeds"]), ("inner", inn)):
            for k, sd in enumerate(seeds, 1):
                z, y, x = sd["zyx"]
                rows.append({"scroll": s["scroll"], "volume": s["volume"], "points_scored": it["seed_summary"]["n_points"],
                             "zone": zone, "rank": k, "x": x, "y": y, "z": z,
                             "score": round(sd["score"], 3), "radius_fraction": round(sd["r_frac"], 3),
                             "height_fraction": round(sd["z_frac"], 3)})
    all_scores = np.concatenate([[p["score"] for p in it["points"] if np.isfinite(p["score"])] for it in items])
    lines += ["", f"{len(items)} volumes, {all_scores.size} scored sample points. 'Share clean' = share of sample points "
              "above 0.63, the score that 75% of the survey's on-sheet seeds exceed."]
    (d / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    with open(d / "seeds.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\n".join(lines[8:]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "atlas", sys.argv[2] if len(sys.argv) > 2 else "atlas_dense")
