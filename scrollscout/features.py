"""Local measures of how cleanly papyrus sheets are separated in a CT neighbourhood.

All functions take a small 3D cube (z, y, x) as a numpy array and return plain floats, so they can
be computed on a laptop CPU for thousands of sample points.

Two inputs are used:

* the published binary surface prediction (``surface-m7``), where a clean region looks like thin,
  parallel, continuous sheets and a crushed region looks like blotchy, fused fragments;
* the CT itself, independently of any model.

The structure tensor of each cube is computed once and reused for every orientation measure
(whole-cube planarity and the per-block normals behind the swirl measure), which makes a point
about 4x cheaper than recomputing it per block.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

_COMPONENTS = ("zz", "yy", "xx", "zy", "zx", "yx")


def tensor_field(vol: np.ndarray, grad_sigma: float = 1.0, int_sigma: float = 4.0, coarse: int = 2) -> dict:
    """The six smoothed components of the 3D structure tensor (float32).

    Gradients are taken at full resolution. The gradient products are then averaged in
    ``coarse``-voxel blocks and smoothed with ``int_sigma / coarse`` on that coarser grid, which is
    close to smoothing with ``int_sigma`` at full resolution and much cheaper. The returned dict
    carries the grid factor under ``"_coarse"``.
    """
    v = vol.astype(np.float32, copy=False)
    g = {
        "z": ndi.gaussian_filter(v, grad_sigma, order=(1, 0, 0)),
        "y": ndi.gaussian_filter(v, grad_sigma, order=(0, 1, 0)),
        "x": ndi.gaussian_filter(v, grad_sigma, order=(0, 0, 1)),
    }
    out = {"_coarse": coarse}
    for c in _COMPONENTS:
        prod = g[c[0]] * g[c[1]]
        if coarse > 1:
            zs, ys, xs = (d // coarse * coarse for d in prod.shape)
            prod = prod[:zs, :ys, :xs].reshape(zs // coarse, coarse, ys // coarse, coarse, xs // coarse, coarse).mean((1, 3, 5))
        out[c] = ndi.gaussian_filter(prod, int_sigma / coarse)
    return out


def _eigs(field: dict, region=(slice(None),) * 3, stride: int = 4):
    """Eigenvalues (descending) and dominant eigenvectors of the tensor on a strided grid of a region.

    ``region`` and ``stride`` are in full-resolution voxels."""
    f = field.get("_coarse", 1)
    sub = tuple(slice(None if s.start is None else s.start // f, None if s.stop is None else s.stop // f,
                      max(1, stride // f)) for s in region)
    c = {k: field[k][sub].ravel() for k in _COMPONENTS}
    T = np.empty((c["zz"].size, 3, 3), np.float32)
    T[:, 0, 0], T[:, 1, 1], T[:, 2, 2] = c["zz"], c["yy"], c["xx"]
    T[:, 0, 1] = T[:, 1, 0] = c["zy"]
    T[:, 0, 2] = T[:, 2, 0] = c["zx"]
    T[:, 1, 2] = T[:, 2, 1] = c["yx"]
    w, vecs = np.linalg.eigh(T)  # ascending
    return w[:, ::-1], vecs[:, :, -1]


def _planarity_from(field, region=(slice(None),) * 3, stride: int = 4) -> tuple[float, np.ndarray]:
    w, n = _eigs(field, region, stride)
    energy = w.sum(1)
    keep = energy > np.percentile(energy, 20)
    w, n, energy = w[keep], n[keep], energy[keep]
    plan = (w[:, 0] - w[:, 1]) / np.maximum(w[:, 0], 1e-6)
    p = float(np.average(plan, weights=energy))
    # sign-invariant mean normal: leading eigenvector of the energy-weighted sum of n n^T
    M = (n[:, :, None] * n[:, None, :] * energy[:, None, None]).sum(0)
    return p, np.linalg.eigh(M)[1][:, -1]


def _dispersion_from(field, vol: np.ndarray, block: int = 48) -> float:
    normals = []
    zs, ys, xs = vol.shape
    for z in range(0, zs - block + 1, block):
        for y in range(0, ys - block + 1, block):
            for x in range(0, xs - block + 1, block):
                region = (slice(z, z + block), slice(y, y + block), slice(x, x + block))
                if vol[region].std() < 1e-3:
                    continue
                normals.append(_planarity_from(field, region)[1])
    if len(normals) < 2:
        return float("nan")
    N = np.array(normals)
    return float(1.0 - np.linalg.eigvalsh((N[:, :, None] * N[:, None, :]).mean(0))[-1])


def planarity(vol: np.ndarray, grad_sigma: float = 1.0, int_sigma: float = 4.0, stride: int = 4) -> tuple[float, np.ndarray]:
    """Energy-weighted mean of (l1 - l2) / l1 and the mean sheet normal.

    1.0 means every gradient points the same way (flat parallel sheets); low values mean the local
    texture has no single orientation (crushed, swirling or blotchy material).
    """
    return _planarity_from(tensor_field(vol, grad_sigma, int_sigma), stride=stride)


def normal_dispersion(vol: np.ndarray, block: int = 48, grad_sigma: float = 1.0, int_sigma: float = 4.0) -> float:
    """How much the sheet orientation turns inside the cube (0 = one orientation, 1 = random).

    The cube is split into blocks; each block gets its dominant normal; the dispersion is
    1 - (largest eigenvalue of the mean n n^T). Swirls and folds give high values.
    """
    return _dispersion_from(tensor_field(vol, grad_sigma, int_sigma), vol, block)


def _ball(radius: int) -> np.ndarray:
    r = np.arange(-radius, radius + 1)
    zz, yy, xx = np.meshgrid(r, r, r, indexing="ij")
    return zz**2 + yy**2 + xx**2 <= radius**2


def prediction_features(pred: np.ndarray, ct_mask: np.ndarray | None = None) -> dict:
    """Measures on the binary surface prediction (0/255)."""
    nan_out = dict(pred_frac=float("nan"), pred_planarity=float("nan"), pred_thick=float("nan"),
                   pred_bigcc=float("nan"), pred_dispersion=float("nan"), pred_ncomp_per_kvox=float("nan"))
    if min(pred.shape, default=0) < 32:  # cube (almost) entirely outside the volume
        return nan_out
    fg = pred > 127
    region = ct_mask if ct_mask is not None else np.ones_like(fg)
    n_region = int(region.sum())
    out = {"pred_frac": float(fg[region].mean()) if n_region else float("nan")}
    if fg.sum() < 100:
        out.update(pred_planarity=float("nan"), pred_thick=float("nan"), pred_bigcc=float("nan"),
                   pred_dispersion=float("nan"))
        return out
    smooth = ndi.gaussian_filter(fg.astype(np.float32), 1.0)
    field = tensor_field(smooth)
    out["pred_planarity"], _ = _planarity_from(field)
    out["pred_dispersion"] = _dispersion_from(field, smooth)
    # fused sheets are thick: share of foreground more than 2 voxels from any background voxel
    # (exactly distance_transform_edt(fg) > 2, computed as an erosion by a radius-2 ball)
    deep = ndi.binary_erosion(fg, structure=_ball(2), border_value=1)
    out["pred_thick"] = float(deep[fg].mean())
    # continuity: share of foreground voxels in components bigger than 2% of the cube's foreground
    lab, nlab = ndi.label(fg)
    if nlab:
        sizes = np.bincount(lab.ravel())[1:]
        out["pred_bigcc"] = float(sizes[sizes > 0.02 * fg.sum()].sum() / fg.sum())
        out["pred_ncomp_per_kvox"] = float(nlab / (fg.sum() / 1000.0))
    else:
        out["pred_bigcc"] = 0.0
        out["pred_ncomp_per_kvox"] = float("nan")
    return out


def ct_features(ct: np.ndarray) -> dict:
    """Measures on the CT itself (no model involved)."""
    if min(ct.shape, default=0) < 32:  # cube (almost) entirely outside the volume
        return dict(ct_valid=0.0, ct_planarity=float("nan"), ct_dispersion=float("nan"), ct_contrast=float("nan"))
    mask = ct > 0  # the published volumes are masked: 0 outside the papyrus
    out = {"ct_valid": float(mask.mean())}
    if mask.mean() < 0.3:
        out.update(ct_planarity=float("nan"), ct_dispersion=float("nan"), ct_contrast=float("nan"))
        return out
    v = ct.astype(np.float32)
    field = tensor_field(v)
    out["ct_planarity"], n = _planarity_from(field)
    out["ct_dispersion"] = _dispersion_from(field, v)
    # sheet/gap modulation along the mean normal: std of the profile along n vs. total std
    c = (np.array(v.shape, dtype=np.float32) - 1) / 2
    t = ((np.arange(v.shape[0], dtype=np.float32) - c[0])[:, None, None] * n[0]
         + (np.arange(v.shape[1], dtype=np.float32) - c[1])[None, :, None] * n[1]
         + (np.arange(v.shape[2], dtype=np.float32) - c[2])[None, None, :] * n[2])
    tb = np.round(t).astype(np.int32)
    tb -= tb.min()
    sums = np.bincount(tb[mask], weights=v[mask])
    cnts = np.bincount(tb[mask])
    prof = sums[cnts > 50] / cnts[cnts > 50]
    out["ct_contrast"] = float(prof.std() / (v[mask].std() + 1e-6)) if prof.size > 8 else float("nan")
    return out
