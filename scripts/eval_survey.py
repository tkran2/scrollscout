"""Compute scout features at every First Letters survey seed and score them against the verdicts.

    python scripts/eval_survey.py --survey <first-letters-survey>/results/results.json \
        --index <villa>/scrollprize.org/static/data_browser/index.json --out results/survey_features.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.catalog import Catalog  # noqa: E402
from scrollscout.features import ct_features, prediction_features  # noqa: E402
from scrollscout.survey import load_patches  # noqa: E402
from scrollscout.zarrhttp import ZArray  # noqa: E402

LEVEL = 1
HALF = 96  # 192^3 voxels at level 1 (~3.3 mm at 8.6 um)


def run_one(args):
    row, index_path, half = args
    cat = Catalog.load(index_path)
    vol = cat.volume(row["scroll"], row["volume"])
    f = 2**LEVEL
    center = [v / f for v in row["seed_zyx"]]
    t = time.time()
    ct = ZArray.open(vol.ct, LEVEL).read_centered(center, half)
    pred = ZArray.open(vol.surface, LEVEL).read_centered(center, half)
    feats = {}
    feats.update(ct_features(ct))
    feats.update(prediction_features(pred, ct > 0))
    out = dict(row)
    out["features"] = feats
    out["secs"] = round(time.time() - t, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--half", type=int, default=HALF)
    a = ap.parse_args()
    rows = load_patches(a.survey)
    done = []
    with ProcessPoolExecutor(a.workers) as pool:
        for i, r in enumerate(pool.map(run_one, [(r, a.index, a.half) for r in rows])):
            done.append(r)
            fs = {k: round(v, 3) for k, v in r["features"].items()}
            print(f"[{i + 1}/{len(rows)}] {r['scroll']} label={r['label']} {r['secs']}s {fs}", flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(done, indent=1, default=list))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
