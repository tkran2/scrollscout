"""Score arbitrary points of a scroll volume with the scout features."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np

from .catalog import Volume
from .features import ct_features, prediction_features
from .score import SCORE_TERMS_SIGNED
from .zarrhttp import ZArray

LEVEL = 1
HALF = 96
VALIDATED_UM = (7.5, 10.0)  # the score was built and tested on 8.64 um and 9.36 um scans


def validated_scan(vol: Volume) -> bool:
    """Whether the volume's voxel size lies in the range the score was validated on (the 8.64 um and 9.36 um
    scans).
    """
    return VALIDATED_UM[0] <= float(vol.voxel_um) <= VALIDATED_UM[1]


@lru_cache(maxsize=64)
def prediction_offset(ct_url: str, pred_url: str) -> int:
    """k such that the prediction's level 0 lies on the CT's level-k grid (0 for most volumes; some
    predictions were computed on a downsampled CT, e.g. ``-L2-`` ones)."""
    ct0, pr0 = ZArray.open(ct_url, 0).shape, ZArray.open(pred_url, 0).shape
    return max(0, int(round(np.log2(ct0[0] / pr0[0]))))


def features_at(vol: Volume, zyx0, level: int = LEVEL, half: int = HALF) -> dict:
    """Scout features of the cube around one point. zyx0 is in level-0 voxels (z, y, x); a cube of side 2 * half
    is read from the CT and from the surface prediction at pyramid `level`, and the CT and prediction
    features come back as one dict.
    """
    f = 2**level
    center = [v / f for v in zyx0]
    k = prediction_offset(vol.ct, vol.surface)
    if k > level:
        raise ValueError(f"the surface prediction is stored {2 ** k}x coarser than the CT, too coarse to compare "
                         f"at pyramid level {level}")
    ct = ZArray.open(vol.ct, level).read_centered(center, half)
    pred = ZArray.open(vol.surface, level - k).read_centered(center, half)  # same grid as CT level `level`
    out = {}
    out.update(ct_features(ct))
    out.update(prediction_features(pred, ct > 0))
    return out


def _job(args):
    vol, zyx0, level, half = args
    t = time.time()
    try:
        feats = features_at(vol, zyx0, level, half)
    except Exception as e:  # keep going on a bad chunk
        feats = {"error": repr(e)}
    feats["secs"] = round(time.time() - t, 1)
    return [int(v) for v in zyx0], feats


def features_at_many(vol: Volume, points, workers: int = 4, level: int = LEVEL, half: int = HALF, log=None):
    """features_at for many points, in `workers` processes. Returns [{'zyx', 'features'}] in input order; a point
    that fails gets {'error': ...} instead of stopping the run, and `log` gets one progress line per
    point.
    """
    rows = []
    with ProcessPoolExecutor(workers) as pool:
        for i, (p, f) in enumerate(pool.map(_job, [(vol, p, level, half) for p in points])):
            rows.append({"zyx": p, "features": f})
            if log:
                log(f"  [{i + 1}/{len(points)}] {vol.scroll} zyx={p} {f.get('secs')}s")
    return rows


class Calibration:
    """Means/SDs of each score term on a reference set, so scores are comparable across scrolls."""

    def __init__(self, stats: dict):
        self.stats = stats

    @classmethod
    def from_rows(cls, feature_rows: list[dict]) -> "Calibration":
        """A calibration from reference feature rows: the mean and standard deviation of each score term."""
        stats = {}
        for name, _ in SCORE_TERMS_SIGNED:
            x = np.array([r.get(name, np.nan) for r in feature_rows], float)
            stats[name] = {"mean": float(np.nanmean(x)), "sd": float(np.nanstd(x))}
        return cls(stats)

    @classmethod
    def load(cls, path) -> "Calibration":
        """Read a calibration.json."""
        return cls(json.loads(Path(path).read_text()))

    def save(self, path):
        """Write the calibration as JSON."""
        Path(path).write_text(json.dumps(self.stats, indent=1))

    def score(self, feats: dict) -> float:
        """The scout score of one point: the mean of the signed z-scores of its finite score terms (NaN if there
        are none). Higher is cleaner; above 0.63 counts as clean.
        """
        zs = []
        for name, sign in SCORE_TERMS_SIGNED:
            v = feats.get(name)
            if v is None or not np.isfinite(v):
                continue
            s = self.stats[name]
            zs.append(sign * (v - s["mean"]) / (s["sd"] or 1.0))
        return float(np.mean(zs)) if zs else float("nan")
