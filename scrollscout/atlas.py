"""Scan a whole scroll volume: sample points through the papyrus, score them, pick seeds."""

from __future__ import annotations

import time

import numpy as np

from .catalog import Volume
from .sampling import CoarseScroll, load_coarse, sample_points
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


def summarize(rows, cal: Calibration, k: int = 5, min_sep_vox: float = 1500) -> dict:
    """Score statistics and the best seeds of a set of scored points."""
    scores = np.array([r["score"] for r in rows], float)
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.5)
    ok = np.isfinite(scores)
    return {
        "n_points": int(ok.sum()),
        "score_median": float(np.median(scores[ok])) if ok.any() else float("nan"),
        "score_p90": float(np.percentile(scores[ok], 90)) if ok.any() else float("nan"),
        "frac_clean": float(np.mean(scores[ok] > thr)) if ok.any() else float("nan"),
        "seeds": [{"zyx": s["zyx"], "xyz": s["zyx"][::-1], "score": s["score"], "r_frac": s["r_frac"],
                   "z_frac": s["z_frac"]} for s in pick_seeds(rows, k, min_sep_vox)],
    }


def scan_volume(vol: Volume, cal: Calibration, n_points: int = 64, workers: int = 4, half: int = HALF,
                seed: int = 0, log=None) -> dict:
    """Score n_points points spread through a volume's papyrus (stratified by height and distance from the axis)
    and pick seeds. Returns {'summary': score statistics and seeds, 'points': every point with its
    features, score and position in the scroll, 'coarse': the scroll's coarse geometry}.
    """
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
    summary = {
        "scroll": vol.scroll,
        "volume": vol.volume,
        "voxel_um": vol.voxel_um,
        "energy_kev": vol.energy_kev,
        "ct": vol.ct,
        "surface": vol.surface,
        **summarize(rows, cal),
        "secs": round(time.time() - t0),
    }
    return {"summary": summary, "points": rows,
            "coarse": {"factor": cs.factor, "center_yx": cs.center_yx.tolist(), "radius": cs.radius.tolist(),
                       "z_extent": cs.z_extent}}


def merge_scans(a: dict, b: dict, cal: Calibration) -> dict:
    """Combine two scans of the same volume (e.g. the atlas pass and a denser follow-up) and redo the summary."""
    rows = a["points"] + b["points"]
    summary = dict(a["summary"])
    summary.update(summarize(rows, cal))
    summary["secs"] = a["summary"].get("secs", 0) + b["summary"].get("secs", 0)
    return {"summary": summary, "points": rows, "coarse": a["coarse"]}


def grid_near(cs: CoarseScroll, center_zyx, step: int = 300, size: int = 3) -> list[list[int]]:
    """A size x size x size grid of level-0 points ``step`` voxels apart centred on a target, nearest
    first, keeping the target and every other point where the coarse CT shows papyrus."""
    offs = (np.arange(size) - (size - 1) / 2) * step
    c = np.asarray(center_zyx, float)
    pts = [c + np.array([dz, dy, dx]) for dz in offs for dy in offs for dx in offs]
    pts.sort(key=lambda p: float(np.linalg.norm(p - c)))
    return [[int(round(v)) for v in p] for i, p in enumerate(pts) if i == 0 or cs.in_papyrus(p)]


def scan_near(vol: Volume, cal: Calibration, center_zyx, step: int = 300, size: int = 3, workers: int = 4,
              log=None) -> dict:
    """Score a small grid around a target (say, where text was seen) and rank the points as seeds."""
    t0 = time.time()
    if vol.surface is None:
        raise ValueError(f"{vol.scroll} {vol.volume}: no published surface prediction")
    cs = load_coarse(vol.ct)
    pts = grid_near(cs, center_zyx, step, size)
    if log:
        log(f"{vol.scroll} ({vol.voxel_um} um): scoring {len(pts)} points around x={center_zyx[2]} "
            f"y={center_zyx[1]} z={center_zyx[0]}, {step} voxels apart")
    rows = features_at_many(vol, pts, workers, LEVEL, HALF, log=log)
    c = np.asarray(center_zyx, float)
    for r in rows:
        r["score"] = cal.score(r["features"])
        r["r_frac"] = cs.radius_fraction(r["zyx"])
        r["z_frac"] = cs.z_fraction(r["zyx"])
        r["dist_vox"] = float(np.linalg.norm(np.asarray(r["zyx"], float) - c))
    target = rows[0]
    summary = {
        "scroll": vol.scroll, "volume": vol.volume, "voxel_um": vol.voxel_um, "energy_kev": vol.energy_kev,
        "ct": vol.ct, "surface": vol.surface, "target_xyz": [int(v) for v in c[::-1]],
        "target_score": target["score"], "target_in_papyrus": cs.in_papyrus(c), "step": step, "size": size,
        **summarize(rows, cal, k=5, min_sep_vox=0),
        "secs": round(time.time() - t0),
    }
    for s in summary["seeds"]:
        s["dist_vox"] = float(np.linalg.norm(np.asarray(s["zyx"], float) - c))
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
