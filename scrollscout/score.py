"""The scout score: one number per neighbourhood, higher = cleaner, more traceable papyrus.

History, kept honest:

* v1 (pre-registered, chosen from first principles before any validation): planarity, swirl,
  fused-sheet and continuity terms of the surface prediction plus CT planarity.
  On the 65 First Letters survey patches: AUC 0.84 (95% CI 0.73-0.93).
* v2 (current): the terms that leave-one-scroll-out cross-validation selects (each chosen on the
  other 20 scrolls only). Held-out AUC 0.88 (0.78-0.95) on scrolls the score never saw.

Each term is z-scored against the survey reference set, signed so that higher = better, and averaged.
"""

from __future__ import annotations

import numpy as np

# (feature, sign): +1 if higher is better
SCORE_TERMS_SIGNED = (
    ("pred_planarity", +1),        # sheets are flat and parallel
    ("pred_dispersion", -1),       # their orientation does not swirl inside the cube
    ("pred_thick", -1),            # sheets are not fused into thick slabs
    ("pred_ncomp_per_kvox", -1),   # few separate fragments per unit of predicted surface
    ("ct_dispersion", -1),         # the CT texture itself does not swirl (model-independent)
)
SCORE_V1_TERMS_SIGNED = (
    ("pred_planarity", +1), ("pred_dispersion", -1), ("pred_thick", -1), ("pred_bigcc", +1), ("ct_planarity", +1),
)
SCORE_TERMS = tuple(f"{'+' if s > 0 else '-'}{k}" for k, s in SCORE_TERMS_SIGNED)


def combined_score(feature_rows: list[dict], reference: list[dict] | None = None, terms=SCORE_TERMS_SIGNED) -> np.ndarray:
    ref = reference if reference is not None else feature_rows
    total = np.zeros(len(feature_rows))
    count = np.zeros(len(feature_rows))
    for name, sign in terms:
        x = np.array([r.get(name, np.nan) for r in feature_rows], float)
        r = np.array([q.get(name, np.nan) for q in ref], float)
        mu, sd = np.nanmean(r), np.nanstd(r)
        z = sign * (x - mu) / (sd if sd > 0 else 1.0)
        ok = np.isfinite(z)
        total[ok] += z[ok]
        count[ok] += 1
    with np.errstate(invalid="ignore"):
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)
