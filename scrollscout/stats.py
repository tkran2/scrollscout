"""Small, dependency-free statistics helpers (AUC, Spearman, bootstrap intervals)."""

from __future__ import annotations

import numpy as np
from scipy import stats as sps


def auc(scores: np.ndarray, positive: np.ndarray) -> float:
    """Area under the ROC curve = P(score of a random positive > score of a random negative)."""
    s = np.asarray(scores, float)
    y = np.asarray(positive, bool)
    ok = np.isfinite(s)
    s, y = s[ok], y[ok]
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = sps.rankdata(s)
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def bootstrap_ci(fn, *arrays, n: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Percentile bootstrap confidence interval (1 - alpha) of fn(*arrays), resampling the rows of all arrays
    together, n times.
    """
    rng = np.random.default_rng(seed)
    arrays = [np.asarray(a) for a in arrays]
    m = len(arrays[0])
    vals = []
    for _ in range(n):
        idx = rng.integers(0, m, m)
        v = fn(*[a[idx] for a in arrays])
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def auc_permutation_p(scores, positive, n: int = 5000, seed: int = 0) -> float:
    """One-sided p-value for AUC > 0.5 under random relabelling."""
    rng = np.random.default_rng(seed)
    s = np.asarray(scores, float)
    y = np.asarray(positive, bool)
    ok = np.isfinite(s)
    s, y = s[ok], y[ok]
    obs = auc(s, y)
    count = 0
    for _ in range(n):
        if auc(s, rng.permutation(y)) >= obs:
            count += 1
    return (count + 1) / (n + 1)


def spearman(a, b) -> float:
    """Spearman rank correlation over the pairs where both values are finite (NaN with fewer than 5 such pairs)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5:
        return float("nan")
    return float(sps.spearmanr(a[ok], b[ok]).statistic)


def zscore(x: np.ndarray, ref: np.ndarray | None = None) -> np.ndarray:
    """(x - mean) / SD, with the mean and SD taken from `ref` (default: x itself), ignoring NaNs."""
    ref = x if ref is None else ref
    mu, sd = np.nanmean(ref), np.nanstd(ref)
    return (x - mu) / (sd if sd > 0 else 1.0)
