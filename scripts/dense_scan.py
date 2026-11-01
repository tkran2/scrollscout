"""Score extra points in the most promising scrolls and merge them with the atlas pass.

    SCROLLSCOUT_NO_CACHE=1 python -I scripts/dense_scan.py --atlas atlas --out atlas_dense \
        --calibration results/calibration.json --points 384 PHerc0306B PHerc0175A PHerc1218
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.atlas import merge_scans, scan_volume  # noqa: E402
from scrollscout.catalog import Catalog  # noqa: E402
from scrollscout.scout import Calibration  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scrolls", nargs="+")
    ap.add_argument("--atlas", default="atlas")
    ap.add_argument("--out", default="atlas_dense")
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--index")
    ap.add_argument("--points", type=int, default=384)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for scroll in a.scrolls:
        base = json.loads((Path(a.atlas) / f"{scroll}.json").read_text())
        vol = cat.volume(scroll, base["summary"]["volume"])
        extra = scan_volume(vol, cal, a.points, a.workers, seed=1,
                            log=lambda m: print(m, flush=True) if not m.startswith("  [") else None)
        merged = merge_scans(base, extra, cal)
        (out / f"{scroll}.json").write_text(json.dumps(merged, indent=1, default=float))
        s = merged["summary"]
        print(f"{scroll}: {s['n_points']} points, median {s['score_median']:.2f}, p90 {s['score_p90']:.2f}, "
              f"clean {s['frac_clean']:.0%}", flush=True)


if __name__ == "__main__":
    main()
