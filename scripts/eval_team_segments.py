"""Independent test: does the scout score separate the team's own good and bad segments?

The Vesuvius Challenge team published 21 automatically grown segments for PHerc. 800 and PHerc. 1447,
two scrolls that played no part in choosing or calibrating the score. The First Letters survey
judged each by eye: 9 follow the sheet, 11 cut obliquely across several layers, 1 is mixed. Each
segment goes through ``scrollscout check-segment`` (12 points spread over its surface); we compare the
segments' median scores and count how many of the tool's verdicts match the survey's.

    python -I scripts/eval_team_segments.py --survey data/first_letters_survey_results.json \
        --index data/catalog_index_2026-10-31.json --calibration results/calibration.json \
        --out results/team_segments.json
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
from scrollscout.stats import auc, auc_permutation_p, bootstrap_ci  # noqa: E402

BUCKET = "s3://vesuvius-challenge-open-data"


def label(verdict: str) -> int | None:
    v = verdict.lower()
    if v.startswith("follows the sheet"):
        return 1
    if "cuts across several layers" in v:
        return 0
    return None  # mixed / ambiguous


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--points", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cat = Catalog.load(a.index)
    cal = Calibration.load(a.calibration)
    segs = json.loads(Path(a.survey).read_text())["published_segments"]
    rows = []
    for s in segs:
        verdict = s["visual_qa"]["surface"]
        try:  # exactly what `scrollscout check-segment <url>` does
            surf = load_surface(f"{BUCKET}/{s['scroll']}/segments/{s['segment']}/")
        except FileNotFoundError:
            print(f"{s['segment']}: no mesh", flush=True)
            continue
        vol = infer_volume(surf, cat)
        res = check_segment(surf, vol, cal, a.points, a.workers)
        sm = res["summary"]
        rows.append({"scroll": s["scroll"], "segment": s["segment"], "volume": vol.volume, "verdict": verdict,
                     "label": label(verdict), "points": res["points"], "scores": [p["score"] for p in res["points"]],
                     "median": sm["median_score"], "frac_clean": sm["frac_clean"], "tool_verdict": sm["verdict"]})
        print(f"{s['scroll']} {s['segment'][:32]:<32} label={label(verdict)} median score {sm['median_score']:+.2f} "
              f"-> {sm['verdict']}", flush=True)
    lab = [r for r in rows if r["label"] is not None]
    y = np.array([r["label"] == 1 for r in lab])
    m = np.array([r["median"] for r in lab])
    res = {"n_good": int(y.sum()), "n_bad": int((~y).sum()), "auc": auc(m, y), "ci": bootstrap_ci(auc, m, y),
           "p": auc_permutation_p(m, y)}
    correct = [(r["tool_verdict"] == FOLLOWS) == (r["label"] == 1) for r in lab]
    res["rule"] = "follows the sheet when the median point scores above the survey-set clean threshold"
    res["rule_correct"] = int(sum(correct))
    res["rule_n"] = len(correct)
    res["unlabelled"] = [{"segment": r["segment"], "verdict": r["verdict"], "tool_verdict": r["tool_verdict"],
                          "median": r["median"], "frac_clean": r["frac_clean"]} for r in rows if r["label"] is None]
    in1447 = np.array([r["scroll"] == "PHerc1447" for r in lab])
    res["auc_within_1447"] = auc(m[in1447], y[in1447])
    res["p_within_1447"] = auc_permutation_p(m[in1447], y[in1447])
    print(f"\nall labelled segments: {res['n_good']} good vs {res['n_bad']} bad, AUC {res['auc']:.3f} "
          f"[{res['ci'][0]:.2f}, {res['ci'][1]:.2f}], permutation p {res['p']:.4f}")
    print(f"within PHerc. 1447 only: AUC {res['auc_within_1447']:.3f}, permutation p {res['p_within_1447']:.4f}")
    print(f"check-segment verdicts (rule fixed beforehand): {res['rule_correct']} of {res['rule_n']} correct")
    Path(a.out).write_text(json.dumps({"summary": res, "segments": rows}, indent=1, default=float))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
