"""Do places where text has actually been found score high?

Two known text locations on 8.64 um / 116 keV scans (the First Letters scan protocol):

* PHerc. 343: the 18 letters of the October 2026 First Letters winner (Nieuwlaar), located on his
  published mesh via his letter boxes.
* PHerc. 1447: the point where the Vesuvius Challenge team announced text on 24 September 2026
  (x 4144, y 2742, z 12557 of volume 20250521151220), plus six points 1.5 mm around it.

Each is compared with randomly placed points inside the same scroll's papyrus.

    python -I scripts/eval_text_regions.py --index data/catalog_index_2026-10-31.json \
        --calibration results/calibration.json --mesh <pherc343 repo>/outputs/concat_...tifxyz \
        --letters <pherc343 repo>/inputs/concat_..._letter_boxes.json --out results/text_regions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.catalog import Catalog  # noqa: E402
from scrollscout.sampling import load_coarse, sample_points  # noqa: E402
from scrollscout.scout import Calibration, features_at_many  # noqa: E402


def mesh_points_from_boxes(mesh_dir: Path, letters_json: Path) -> list[list[int]]:
    import tifffile

    meta = json.loads((mesh_dir / "meta.json").read_text())
    scale = float(meta["scale"][0])
    X, Y, Z = (tifffile.imread(mesh_dir / f"{a}.tif").astype(np.float64) for a in "xyz")
    valid = (X >= 0) & (Y >= 0) & (Z >= 0)
    boxes = json.loads(letters_json.read_text())["letters"]
    pts = []
    for b in boxes:
        x0, y0, x1, y1 = b["box"]  # render pixels, raw frame: (col, row)
        col, row = (x0 + x1) / 2 * scale, (y0 + y1) / 2 * scale
        r, c = int(round(row)), int(round(col))
        if 0 <= r < X.shape[0] and 0 <= c < X.shape[1] and valid[r, c]:
            pts.append([int(round(Z[r, c])), int(round(Y[r, c])), int(round(X[r, c]))])
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--letters", required=True)
    ap.add_argument("--n-random", type=int, default=48)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    log = lambda s: print(s, flush=True)  # noqa: E731

    p1447 = np.array([12557, 2742, 4144])
    off = 1500 / 8.64  # 1.5 mm in voxels
    targets = {
        "PHerc0343": ("20250521140437", mesh_points_from_boxes(Path(a.mesh), Path(a.letters))),
        "PHerc1447": ("20250521151220", [list(p1447)] + [list(p1447 + d) for d in
                      (np.array(v) * off for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]),
    }
    report = {}
    for scroll, (vid, text_pts) in targets.items():
        vol = cat.volume(scroll, vid)
        log(f"{scroll}: {len(text_pts)} text points")
        text_rows = features_at_many(vol, [np.round(p).astype(int) for p in text_pts], a.workers, log=log)
        cs = load_coarse(vol.ct)
        rand = sample_points(cs, a.n_random, seed=1)
        rand_rows = features_at_many(vol, rand, a.workers, log=log)
        ts = np.array([cal.score(r["features"]) for r in text_rows])
        rs = np.array([cal.score(r["features"]) for r in rand_rows])
        rs = rs[np.isfinite(rs)]
        med = float(np.nanmedian(ts))
        pct = float((rs < med).mean() * 100)
        log(f"{scroll}: text median score {med:.2f}; random median {np.median(rs):.2f}; text beats {pct:.0f}% of random points")
        report[scroll] = {
            "volume": vid,
            "text_points": text_rows,
            "random_points": rand_rows,
            "text_scores": ts.tolist(),
            "random_scores": rs.tolist(),
            "text_median": med,
            "random_median": float(np.median(rs)),
            "percentile_of_text_median": pct,
            "text_radius_fraction": [cs.radius_fraction(p) for p in text_pts],
        }
    Path(a.out).write_text(json.dumps(report, indent=1, default=float))
    log(f"wrote {a.out}")


if __name__ == "__main__":
    main()
