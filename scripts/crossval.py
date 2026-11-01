"""Honest test of a data-driven score: leave-one-scroll-out cross-validation.

For each scroll, the features and their signs are chosen on the OTHER scrolls only (keep a feature if
its training AUC is >= 0.70 or <= 0.30), z-scored with training statistics, averaged, and applied to the
held-out scroll's patches. The pooled held-out AUC estimates performance on a scroll the score has
never seen, which is exactly the atlas use case.

    python -I scripts/crossval.py results/survey_features.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.stats import auc, auc_permutation_p, bootstrap_ci, spearman  # noqa: E402

CANDIDATES = ["pred_planarity", "pred_dispersion", "pred_thick", "pred_bigcc", "pred_frac", "pred_ncomp_per_kvox",
              "ct_planarity", "ct_dispersion", "ct_contrast"]


def fit(rows_train, good_train):
    chosen = []
    for k in CANDIDATES:
        x = np.array([r["features"].get(k, np.nan) for r in rows_train], float)
        a = auc(x, good_train)
        if np.isfinite(a) and (a >= 0.70 or a <= 0.30):
            chosen.append((k, 1 if a >= 0.5 else -1, float(np.nanmean(x)), float(np.nanstd(x) or 1.0)))
    return chosen


def apply(model, rows):
    out = []
    for r in rows:
        zs = [s * (r["features"].get(k, np.nan) - mu) / sd for k, s, mu, sd in model]
        zs = [z for z in zs if np.isfinite(z)]
        out.append(np.mean(zs) if zs else np.nan)
    return np.array(out)


def main(path):
    rows = json.loads(Path(path).read_text())
    label = np.array([r["label"] for r in rows])
    good = label >= 2
    scrolls = np.array([r["scroll"] for r in rows])
    held = np.full(len(rows), np.nan)
    picks = {}
    for s in np.unique(scrolls):
        te = scrolls == s
        model = fit([r for r, t in zip(rows, ~te) if t], good[~te])
        held[te] = apply(model, [r for r, t in zip(rows, te) if t])
        for k, sign, *_ in model:
            picks[(k, sign)] = picks.get((k, sign), 0) + 1
    a = auc(held, good)
    lo, hi = bootstrap_ci(auc, held, good)
    p = auc_permutation_p(held, good)
    print(f"leave-one-scroll-out AUC {a:.3f} [{lo:.2f}, {hi:.2f}], permutation p {p:.4f}, "
          f"spearman vs 0-3 label {spearman(held, label):.3f}")
    n_scrolls = len(np.unique(scrolls))
    print("features chosen (times out of", n_scrolls, "folds):")
    for (k, sign), n in sorted(picks.items(), key=lambda t: -t[1]):
        print(f"  {'+' if sign > 0 else '-'}{k}: {n}")
    final = fit(rows, good)
    print("final model on all data:", [(('+' if s > 0 else '-') + k) for k, s, *_ in final])
    order = np.argsort(-held)
    for k in (10, 20):
        print(f"  top {k} held-out seeds: {good[order[:k]].mean():.0%} stayed on the sheet (base rate {good.mean():.0%})")
    Path(path).with_name("crossval.json").write_text(json.dumps(
        {"auc": a, "ci": [lo, hi], "p": p, "held_out_scores": held.tolist(),
         "final_model": [{"feature": k, "sign": s, "mean": mu, "sd": sd} for k, s, mu, sd in final],
         "picks": {f"{'+' if s > 0 else '-'}{k}": n for (k, s), n in picks.items()}}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
