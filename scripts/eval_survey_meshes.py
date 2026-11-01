"""check-segment on the 65 First Letters survey patches, scored over their whole surface.

Each patch's tifxyz (published in the survey repository) goes through ``scrollscout check-segment``:
12 points spread over the patch rather than the single seed point the other survey analyses use.
The score's terms and clean threshold were chosen on these patches' seeds, so this is a consistency
check across all 21 scrolls, not an independent test (those are the team segments and the known
text).

    SCROLLSCOUT_NO_CACHE=1 python -I scripts/eval_survey_meshes.py --survey-repo path/to/first-letters-survey \
        --calibration results/calibration.json --out results/survey_meshes.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.catalog import Catalog  # noqa: E402
from scrollscout.scout import Calibration  # noqa: E402
from scrollscout.segment import FOLLOWS, check_segment, infer_volume, load_surface  # noqa: E402
from scrollscout.stats import auc, auc_permutation_p, bootstrap_ci, spearman  # noqa: E402
from scrollscout.survey import MOSTLY, load_patches  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey-repo", required=True, help="clone of github.com/Bullo27/first-letters-survey")
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--index")
    ap.add_argument("--points", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    repo = Path(a.survey_repo)
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    out = Path(a.out)
    done = {r["tifxyz"]: r for r in json.loads(out.read_text())["patches"]} if out.exists() else {}
    rows = []
    for p in load_patches(repo / "results" / "results.json"):
        if p["tifxyz"] in done:
            rows.append(done[p["tifxyz"]])
            continue
        surf = load_surface(str(repo / p["tifxyz"]))
        vol = infer_volume(surf, cat, p["scroll"], p["volume"])
        res = check_segment(surf, vol, cal, a.points, a.workers)
        s = res["summary"]
        rows.append({"scroll": p["scroll"], "volume": p["volume"], "tifxyz": p["tifxyz"], "label": p["label"],
                     "verdict": p["verdict"], "median": s["median_score"], "frac_clean": s["frac_clean"],
                     "tool_verdict": s["verdict"], "points": res["points"]})
        print(f"{p['tifxyz'].split('/')[-1]:<28} label={p['label']} median {s['median_score']:+.2f} "
              f"clean {s['frac_clean']:.0%} -> {s['verdict']}", flush=True)
        out.write_text(json.dumps({"patches": rows}, indent=1, default=float))  # resumable
    ok = [r for r in rows if np.isfinite(r["median"])]
    y = np.array([r["label"] >= MOSTLY for r in ok])
    m = np.array([r["median"] for r in ok])
    lab = np.array([r["label"] for r in ok], float)
    follows = np.array([r["tool_verdict"] == FOLLOWS for r in ok])
    res = {"n": len(ok), "n_good": int(y.sum()), "auc": auc(m, y), "ci": bootstrap_ci(auc, m, y),
           "p": auc_permutation_p(m, y), "spearman_vs_ordinal_label": spearman(m, lab),
           "rule_sensitivity": float(follows[y].mean()), "rule_specificity": float((~follows[~y]).mean()),
           "rule_precision": float(y[follows].mean()) if follows.any() else float("nan"),
           "n_flagged_follows": int(follows.sum()), "base_rate": float(y.mean())}
    print(f"\n{res['n']} patches ({res['n_good']} stayed on the sheet): AUC {res['auc']:.3f} "
          f"[{res['ci'][0]:.2f}, {res['ci'][1]:.2f}], p {res['p']:.4f}; Spearman vs label {res['spearman_vs_ordinal_label']:.2f}")
    print(f"verdict 'follows the sheet' for {res['n_flagged_follows']} patches, {res['rule_precision']:.0%} of them "
          f"right (base rate {res['base_rate']:.0%}); catches {res['rule_sensitivity']:.0%} of good patches, "
          f"clears {res['rule_specificity']:.0%} of bad ones")
    out.write_text(json.dumps({"summary": res, "patches": rows}, indent=1, default=float))
    print("wrote", out)


if __name__ == "__main__":
    main()
