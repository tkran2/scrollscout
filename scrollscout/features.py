"""Local measures of how cleanly papyrus sheets are separated in a CT neighbourhood.

All functions take a small 3D cube (z, y, x) as a numpy array and return plain floats, so they can
be computed on a laptop CPU for thousands of sample points.

Two inputs are used:

* the published binary surface prediction (``surface-m7``), where a clean region looks like thin,
  parallel, continuous sheets and a crushed region looks like blotchy, fused fragments;
* the CT itself, independently of any model.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def _structure_tensor_eigs(vol: np.ndarray, grad_sigma: float, int_sigma: float, stride: int = 1):
    """Eigenvalues (descending) and dominant eigenvector of the 3D structure tensor, on a voxel grid
    subsampled by ``stride`` (the tensor is smoothed first, so subsampling loses little)."""
    v = vol.astype(np.float32)
    gz = ndi.gaussian_filter(v, grad_sigma, order=(1, 0, 0))
    gy = ndi.gaussian_filter(v, grad_sigma, order=(0, 1, 0))
    gx = ndi.gaussian_filter(v, grad_sigma, order=(0, 0, 1))
    comps = {}
    sub = slice(None, None, stride)
    for name, a, b in (("zz", gz, gz), ("yy", gy, gy), ("xx", gx, gx), ("zy", gz, gy), ("zx", gz, gx), ("yx", gy, gx)):
        comps[name] = ndi.gaussian_filter(a * b, int_sigma)[sub, sub, sub]
    T = np.stack(
        [
            np.stack([comps["zz"], comps["zy"], comps["zx"]], -1),
            np.stack([comps["zy"], comps["yy"], comps["yx"]], -1),
            np.stack([comps["zx"], comps["yx"], comps["xx"]], -1),
        ],
        -2,
    )
    T = T.reshape(-1, 3, 3)
    w, vecs = np.linalg.eigh(T)  # ascending
    w = w[:, ::-1]
    n = vecs[:, :, -1]  # eigenvector of the largest eigenvalue = sheet normal
    return w, n


def planarity(vol: np.ndarray, grad_sigma: float = 1.0, int_sigma: float = 4.0, stride: int = 4) -> tuple[float, np.ndarray]:
    """Energy-weighted mean of (l1 - l2) / l1 and the mean sheet normal.

    1.0 means every gradient points the same way (flat parallel sheets); low values mean the local
    texture has no single orientation (crushed, swirling or blotchy material).
    """
    w, n = _structure_tensor_eigs(vol, grad_sigma, int_sigma, stride=stride)
    energy = w.sum(1)
    keep = energy > np.percentile(energy, 20)
    w, n, energy = w[keep], n[keep], energy[keep]
    plan = (w[:, 0] - w[:, 1]) / np.maximum(w[:, 0], 1e-6)
    p = float(np.average(plan, weights=energy))
    # orientation-consistent mean normal (sign-invariant): leading eigenvector of sum n n^T
    M = (n[:, :, None] * n[:, None, :] * energy[:, None, None]).sum(0)
    ev, evec = np.linalg.eigh(M)
    return p, evec[:, -1]


def normal_dispersion(vol: np.ndarray, block: int = 48, **kw) -> float:
    """How much the sheet orientation turns inside the cube (0 = one orientation, 1 = random).

    The cube is split into blocks; each block gets its dominant normal; the dispersion is
    1 - (largest eigenvalue of the mean n n^T). Swirls and folds give high values.
    """
    normals = []
    zs, ys, xs = vol.shape
    for z in range(0, zs - block + 1, block):
        for y in range(0, ys - block + 1, block):
            for x in range(0, xs - block + 1, block):
                b = vol[z : z + block, y : y + block, x : x + block]
                if b.std() < 1e-3:
                    continue
                _, n = planarity(b, stride=4, **kw)
                normals.append(n)
    if len(normals) < 2:
        return float("nan")
    N = np.array(normals)
    M = (N[:, :, None] * N[:, None, :]).mean(0)
    return float(1.0 - np.linalg.eigvalsh(M)[-1])


def prediction_features(pred: np.ndarray, ct_mask: np.ndarray | None = None) -> dict:
    """Measures on the binary surface prediction (0/255)."""
    fg = pred > 127
    region = ct_mask if ct_mask is not None else np.ones_like(fg)
    n_region = int(region.sum())
    out = {"pred_frac": float(fg[region].mean()) if n_region else float("nan")}
    if fg.sum() < 100:
        out.update(pred_planarity=float("nan"), pred_thick=float("nan"), pred_bigcc=float("nan"), pred_dispersion=float("nan"))
        return out
    smooth = ndi.gaussian_filter(fg.astype(np.float32), 1.0)
    out["pred_planarity"], _ = planarity(smooth, grad_sigma=1.0, int_sigma=4.0)
    out["pred_dispersion"] = normal_dispersion(smooth, block=48, grad_sigma=1.0, int_sigma=4.0)
    # fused sheets are thick: fraction of foreground deeper than 2 voxels from the boundary
    edt = ndi.distance_transform_edt(fg)
    out["pred_thick"] = float((edt[fg] > 2.0).mean())
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
    mask = ct > 0  # the published volumes are masked: 0 outside the papyrus
    out = {"ct_valid": float(mask.mean())}
    if mask.mean() < 0.3:
        out.update(ct_planarity=float("nan"), ct_dispersion=float("nan"), ct_contrast=float("nan"))
        return out
    v = ct.astype(np.float32)
    out["ct_planarity"], n = planarity(v, grad_sigma=1.0, int_sigma=4.0)
    out["ct_dispersion"] = normal_dispersion(v, block=48, grad_sigma=1.0, int_sigma=4.0)
    # sheet/gap modulation along the mean normal: std of the profile along n vs. total std
    zz, yy, xx = np.indices(v.shape, dtype=np.float32)
    c = (np.array(v.shape, dtype=np.float32) - 1) / 2
    t = (zz - c[0]) * n[0] + (yy - c[1]) * n[1] + (xx - c[2]) * n[2]
    tb = np.round(t).astype(np.int32)
    tb -= tb.min()
    sel = mask
    sums = np.bincount(tb[sel], weights=v[sel])
    cnts = np.bincount(tb[sel])
    prof = sums[cnts > 50] / cnts[cnts > 50]
    out["ct_contrast"] = float(prof.std() / (v[sel].std() + 1e-6)) if prof.size > 8 else float("nan")
    return out
