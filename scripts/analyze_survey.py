"""How well does each scout feature predict whether a GrowPatch seed stays on the sheet?

    python scripts/analyze_survey.py results/survey_features.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.score import SCORE_TERMS_SIGNED, SCORE_V1_TERMS_SIGNED, combined_score  # noqa: E402
from scrollscout.stats import auc, auc_permutation_p, bootstrap_ci, spearman  # noqa: E402


def main(path: str):
    rows = json.loads(Path(path).read_text())
    label = np.array([r["label"] for r in rows])
    good = label >= 2
    feats = sorted({k for r in rows for k in r["features"]})
    print(f"{len(rows)} patches: {good.sum()} stayed on the sheet (label >= 2), {(~good).sum()} did not\n")
    print(f"{'feature':<22}{'AUC':>7}  {'95% CI':<15}{'spearman':>9}  direction")
    table = {}
    for k in feats:
        x = np.array([r["features"].get(k, np.nan) for r in rows], float)
        a = auc(x, good)
        lo, hi = bootstrap_ci(auc, x, good)
        rho = spearman(x, label)
        table[k] = dict(auc=a, ci=(lo, hi), spearman=rho)
        print(f"{k:<22}{a:7.3f}  [{lo:.2f}, {hi:.2f}]   {rho:8.3f}  {'higher = better' if a >= 0.5 else 'lower = better'}")

    results = {}
    for name, terms in (("v1_preregistered", SCORE_V1_TERMS_SIGNED), ("v2_in_sample", SCORE_TERMS_SIGNED)):
        score = combined_score([r["features"] for r in rows], terms=terms)
        a = auc(score, good)
        lo, hi = bootstrap_ci(auc, score, good)
        p = auc_permutation_p(score, good)
        rho = spearman(score, label)
        order = np.argsort(-score)
        top10 = float(good[order[:10]].mean())
        results[name] = dict(auc=a, ci=(lo, hi), p=p, spearman=rho, top10=top10)
        terms_txt = " ".join(("+" if sg > 0 else "-") + k for k, sg in terms)
        print(f"\n{name} ({terms_txt}):")
        print(f"  AUC {a:.3f} [{lo:.2f}, {hi:.2f}], permutation p = {p:.4f}, spearman vs 0-3 label = {rho:.3f}, "
              f"top-10 precision {top10:.0%} (base rate {good.mean():.0%})")
    out = Path(path).with_name("survey_analysis.json")
    out.write_text(json.dumps(dict(features=table, combined=results["v1_preregistered"], **results), indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
