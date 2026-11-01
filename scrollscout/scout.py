"""Score arbitrary points of a scroll volume with the scout features."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .catalog import Volume
from .features import ct_features, prediction_features
from .score import SCORE_TERMS_SIGNED
from .zarrhttp import ZArray

LEVEL = 1
HALF = 96


def features_at(vol: Volume, zyx0, level: int = LEVEL, half: int = HALF) -> dict:
    f = 2**level
    center = [v / f for v in zyx0]
    ct = ZArray.open(vol.ct, level).read_centered(center, half)
    pred = ZArray.open(vol.surface, level).read_centered(center, half)
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
        stats = {}
        for name, _ in SCORE_TERMS_SIGNED:
            x = np.array([r.get(name, np.nan) for r in feature_rows], float)
            stats[name] = {"mean": float(np.nanmean(x)), "sd": float(np.nanstd(x))}
        return cls(stats)

    @classmethod
    def load(cls, path) -> "Calibration":
        return cls(json.loads(Path(path).read_text()))

    def save(self, path):
        Path(path).write_text(json.dumps(self.stats, indent=1))

    def score(self, feats: dict) -> float:
        zs = []
        for name, sign in SCORE_TERMS_SIGNED:
            v = feats.get(name)
            if v is None or not np.isfinite(v):
                continue
            s = self.stats[name]
            zs.append(sign * (v - s["mean"]) / (s["sd"] or 1.0))
        return float(np.mean(zs)) if zs else float("nan")
