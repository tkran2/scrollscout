"""Score sample points throughout every prize-eligible scroll volume and pick the best seeds.

Same as ``scrollscout atlas``; kept as a script so the README's reproduction steps are explicit.

    SCROLLSCOUT_NO_CACHE=1 python -I scripts/build_atlas.py --index data/catalog_index_2026-10-31.json \
        --eligibility data/prize_eligibility_2026-10-31.json --calibration results/calibration.json \
        --points 64 --out atlas/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.atlas import scan_volume  # noqa: E402
from scrollscout.catalog import Catalog  # noqa: E402
from scrollscout.scout import HALF, Calibration  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--eligibility", required=True)
    ap.add_argument("--prize", default="first-letters-2027")
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--points", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--half", type=int, default=HALF)
    ap.add_argument("--only", nargs="*", help="scroll ids to (re)run")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for e in json.loads(Path(a.eligibility).read_text())[a.prize]:
        scroll, vid = e["scroll"], e["volume"]
        if a.only and scroll not in a.only:
            continue
        dst = out / f"{scroll}.json"
        if dst.exists() and not a.only:
            print(f"{scroll}: done already", flush=True)
            continue
        res = scan_volume(cat.volume(scroll, vid), cal, a.points, a.workers, a.half,
                          log=lambda m: print(m, flush=True) if not m.startswith("  [") else None)
        dst.write_text(json.dumps(res, indent=1, default=float))
        s = res["summary"]
        print(f"{scroll}: median {s['score_median']:.2f}, p90 {s['score_p90']:.2f}, "
              f"clean {s['frac_clean']:.0%}, {s['secs']}s", flush=True)


if __name__ == "__main__":
    main()
