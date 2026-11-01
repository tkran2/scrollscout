"""Scan a whole scroll volume: sample points through the papyrus, score them, pick seeds."""

from __future__ import annotations

import time

import numpy as np

from .catalog import Volume
from .sampling import load_coarse, sample_points
from .scout import HALF, LEVEL, Calibration, features_at_many


def pick_seeds(rows, k: int = 5, min_sep_vox: float = 1500) -> list[dict]:
    """Best-scoring points, at least ``min_sep_vox`` level-0 voxels apart (~13 mm at 8.64 um)."""
    good = sorted((r for r in rows if np.isfinite(r["score"])), key=lambda r: -r["score"])
    seeds = []
    for r in good:
        p = np.array(r["zyx"], float)
        if all(np.linalg.norm(p - np.array(s["zyx"], float)) >= min_sep_vox for s in seeds):
            seeds.append(r)
        if len(seeds) == k:
            break
    return seeds


INNER_R = 0.45
INNER_Z = (0.15, 0.85)


def inner_seeds(points, k: int = 3) -> list[dict]:
    """Best points in the inner part of the scroll (radius fraction <= 0.45, away from the top and bottom
    15%): both known text finds on the 116 keV protocol lie in this zone."""
    rows = [p for p in points if np.isfinite(p.get("score", np.nan)) and np.isfinite(p.get("r_frac", np.nan))
            and p["r_frac"] <= INNER_R and INNER_Z[0] <= p["z_frac"] <= INNER_Z[1]]
    return pick_seeds(rows, k=k)


def scan_volume(vol: Volume, cal: Calibration, n_points: int = 64, workers: int = 4, half: int = HALF,
                seed: int = 0, log=None) -> dict:
    t0 = time.time()
    if vol.surface is None:
        raise ValueError(f"{vol.scroll} {vol.volume}: no published surface prediction")
    cs = load_coarse(vol.ct)
    pts = sample_points(cs, n_points, seed=seed)
    if log:
        log(f"{vol.scroll} ({vol.voxel_um} um, {vol.energy_kev} keV): scoring {len(pts)} points")
    rows = features_at_many(vol, pts, workers, LEVEL, half, log=log)
    for r in rows:
        r["score"] = cal.score(r["features"])
        r["r_frac"] = cs.radius_fraction(r["zyx"])
        r["z_frac"] = cs.z_fraction(r["zyx"])
    scores = np.array([r["score"] for r in rows], float)
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.5)
    seeds = pick_seeds(rows)
    summary = {
        "scroll": vol.scroll,
        "volume": vol.volume,
        "voxel_um": vol.voxel_um,
        "energy_kev": vol.energy_kev,
        "ct": vol.ct,
        "surface": vol.surface,
        "n_points": int(np.isfinite(scores).sum()),
        "score_median": float(np.nanmedian(scores)),
        "score_p90": float(np.nanpercentile(scores, 90)),
        "frac_clean": float(np.nanmean(scores > thr)),
        "seeds": [{"zyx": s["zyx"], "xyz": s["zyx"][::-1], "score": s["score"], "r_frac": s["r_frac"],
                   "z_frac": s["z_frac"]} for s in seeds],
        "secs": round(time.time() - t0),
    }
    return {"summary": summary, "points": rows,
            "coarse": {"factor": cs.factor, "center_yx": cs.center_yx.tolist(), "radius": cs.radius.tolist(),
                       "z_extent": cs.z_extent}}


def seed_commands(summary: dict, top: int = 5) -> list[str]:
    """Ready-to-run commands that grow a patch from each seed (first-letters-survey's fls.py)."""
    out = []
    for i, s in enumerate(summary["seeds"][:top], 1):
        x, y, z = s["xyz"]
        out.append(f"python fls.py run --scroll {summary['scroll']} --seed {x} {y} {z} --gens 100 --name scout_{i}")
    return out
