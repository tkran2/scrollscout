"""Where is the papyrus? Coarse masks, scroll axis estimates and sample points.

Everything here works on the coarsest pyramid level of the CT (level 5, ~276 um voxels for an
8.64 um scan), which is a ~70 MB download per scroll.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .zarrhttp import ZArray


@dataclass
class CoarseScroll:
    level: int
    factor: int  # level-0 voxels per coarse voxel
    vol: np.ndarray  # coarse CT (z, y, x), uint8
    mask: np.ndarray  # papyrus mask (bool)
    inner: np.ndarray  # mask eroded away from the outer surface and air gaps (bool)
    center_yx: np.ndarray  # per-z centre of the papyrus cross-section (coarse voxels), NaN where empty
    radius: np.ndarray  # per-z outer radius (coarse voxels)
    z_extent: tuple[int, int]  # first/last coarse z with papyrus

    def to_level0(self, zyx) -> np.ndarray:
        return (np.asarray(zyx, float) + 0.5) * self.factor

    def radius_fraction(self, zyx0) -> float:
        """Radius of a level-0 point relative to the outer radius at its height (0 = axis, 1 = outside)."""
        z, y, x = np.asarray(zyx0, float) / self.factor
        zi = int(np.clip(round(z), 0, len(self.radius) - 1))
        c = self.center_yx[zi]
        if not np.all(np.isfinite(c)) or self.radius[zi] <= 0:
            return float("nan")
        return float(np.hypot(y - c[0], x - c[1]) / self.radius[zi])

    def z_fraction(self, zyx0) -> float:
        z = zyx0[0] / self.factor
        a, b = self.z_extent
        return float((z - a) / max(1, b - a))


def load_coarse(ct_url: str, level: int = 5, erode_vox: int = 2) -> CoarseScroll:
    za = ZArray.open(ct_url, level)
    vol = za.read(0, za.shape[0], 0, za.shape[1], 0, za.shape[2])
    factor = 2**level
    mask = vol > 0
    mask = ndi.binary_opening(mask, iterations=1)
    # keep the largest component (the scroll), drop specks
    lab, n = ndi.label(mask)
    if n > 1:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        mask = lab == sizes.argmax()
    filled = np.stack([ndi.binary_fill_holes(s) for s in mask])
    inner = ndi.binary_erosion(mask, iterations=erode_vox)
    center = np.full((vol.shape[0], 2), np.nan)
    radius = np.zeros(vol.shape[0])
    for z in range(vol.shape[0]):
        if filled[z].sum() < 20:
            continue
        yy, xx = np.nonzero(filled[z])
        cy, cx = yy.mean(), xx.mean()
        center[z] = (cy, cx)
        radius[z] = np.percentile(np.hypot(yy - cy, xx - cx), 99)
    zs = np.nonzero(radius > 0)[0]
    z_extent = (int(zs.min()), int(zs.max())) if zs.size else (0, vol.shape[0] - 1)
    return CoarseScroll(level, factor, vol, mask, inner, center, radius, z_extent)


def sample_points(cs: CoarseScroll, n: int, seed: int = 0, z_margin: float = 0.08, r_max: float = 0.95) -> np.ndarray:
    """Spread ``n`` level-0 points through the papyrus, stratified by height and radius.

    Points avoid the top/bottom ``z_margin`` of the scroll and the outermost shell (``r_max``).
    """
    rng = np.random.default_rng(seed)
    zz, yy, xx = np.nonzero(cs.inner)
    a, b = cs.z_extent
    zf = (zz + 0.5 - a) / max(1, b - a)
    cy, cx = cs.center_yx[zz, 0], cs.center_yx[zz, 1]
    rad = cs.radius[zz]
    with np.errstate(invalid="ignore", divide="ignore"):
        rf = np.hypot(yy + 0.5 - cy, xx + 0.5 - cx) / np.where(rad > 0, rad, np.nan)
    ok = (zf > z_margin) & (zf < 1 - z_margin) & np.isfinite(rf) & (rf < r_max)
    pts0 = cs.to_level0(np.stack([zz[ok], yy[ok], xx[ok]], 1))
    zf, rf = zf[ok], rf[ok]
    # stratify: 8 height bins x 4 radius bins, as even as the papyrus allows
    zb = np.minimum((zf - z_margin) / (1 - 2 * z_margin) * 8, 7).astype(int)
    rb = np.minimum(rf / r_max * 4, 3).astype(int)
    cell = zb * 4 + rb
    cells = np.unique(cell)
    per = max(1, n // len(cells))
    chosen = []
    for c in cells:
        idx = np.nonzero(cell == c)[0]
        chosen.extend(rng.choice(idx, size=min(per, idx.size), replace=False))
    chosen = np.array(chosen)
    if chosen.size > n:
        chosen = rng.choice(chosen, size=n, replace=False)
    # jitter inside the coarse voxel so points do not sit on a lattice
    jitter = rng.uniform(-0.5, 0.5, size=(chosen.size, 3)) * cs.factor
    return np.round(pts0[chosen] + jitter).astype(int)
