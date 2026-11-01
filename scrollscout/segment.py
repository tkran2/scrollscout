"""Check a traced segment before spending GPU time on ink detection.

A segment is a surface grown by VC3D's GrowPatch, ``fls.py`` or any other tracer, stored as a
tifxyz folder (``x.tif``, ``y.tif``, ``z.tif``, ``meta.json``) or an OBJ mesh. We score points spread
evenly over it. A segment that runs through clean papyrus follows its sheet; one that runs through
crushed papyrus is the kind that hops between layers.

Rule (fixed before it was tested): a segment *likely follows the sheet* when its median point
scores above the clean threshold (0.63, set on the First Letters survey). Applied to the 20
auto-grown segments the team published for PHerc. 800 and 1447, scrolls the score never saw, it
classifies all 20 correctly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .catalog import Catalog, Volume, list_prefixes
from .scout import Calibration, features_at_many, validated_scan
from .zarrhttp import BUCKET_HTTPS, _get, default_cache_dir, to_https

FOLLOWS, CROSSES = "likely follows the sheet", "likely cuts across layers"
NO_PAPYRUS = 0.05  # below this share of non-zero CT voxels, a point's cube is outside the scroll or the scan


@dataclass
class Surface:
    """Valid nodes of a segment: positions (z, y, x in level-0 voxels) and 2-D map coordinates."""

    name: str
    zyx: np.ndarray  # (n, 3)
    uv: np.ndarray  # (n, 2): grid (row, col) for tifxyz, texture or projected coordinates for OBJ
    grid_shape: tuple[int, int] | None = None  # tifxyz only
    meta: dict = field(default_factory=dict)
    source: str = ""

    @property
    def area_cm2(self) -> float | None:
        a = self.meta.get("area_cm2")
        return float(a) if a is not None else None


def read_tifxyz(folder) -> Surface:
    try:
        import tifffile
    except ImportError as e:  # pragma: no cover
        raise ImportError("reading tifxyz needs tifffile and imagecodecs: pip install tifffile imagecodecs") from e
    folder = Path(folder)
    X, Y, Z = (tifffile.imread(folder / f"{a}.tif").astype(np.float64) for a in "xyz")
    ok = (X >= 0) & (Y >= 0) & (Z >= 0) & np.isfinite(X) & np.isfinite(Y) & np.isfinite(Z)
    rr, cc = np.nonzero(ok)
    meta = json.loads((folder / "meta.json").read_text()) if (folder / "meta.json").exists() else {}
    zyx = np.stack([Z[rr, cc], Y[rr, cc], X[rr, cc]], 1)
    return Surface(folder.name, zyx, np.stack([rr, cc], 1).astype(float), X.shape, meta, str(folder))


def read_obj(path) -> Surface:
    """Vertices of an OBJ mesh (x y z in level-0 voxels); texture coordinates for the map when present."""
    path = Path(path)
    v, vt, v2t = [], [], {}
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                v.append([float(t) for t in line.split()[1:4]])
            elif line.startswith("vt "):
                vt.append([float(t) for t in line.split()[1:3]])
            elif line.startswith("f ") and vt:
                for corner in line.split()[1:]:
                    parts = corner.split("/")
                    if len(parts) > 1 and parts[1]:
                        v2t.setdefault(int(parts[0]) - 1, int(parts[1]) - 1)
    xyz = np.array(v, float)
    if not len(xyz):
        raise ValueError(f"{path}: no vertices")
    if vt and len(v2t) == len(xyz):
        tex = np.array(vt, float)
        uv = tex[[v2t[i] for i in range(len(xyz))]][:, ::-1]
    elif len(vt) == len(xyz):
        uv = np.array(vt, float)[:, ::-1]
    else:  # project onto the best-fitting plane
        c = xyz - xyz.mean(0)
        _, _, vh = np.linalg.svd(c[:: max(1, len(c) // 20000)], full_matrices=False)
        uv = c @ vh[:2].T
    return Surface(path.stem, xyz[:, ::-1].copy(), uv, None, {}, str(path))


def fetch_segment(url: str) -> Path:
    """Download a tifxyz from the open-data bucket into the cache and return its folder.

    ``url`` is an s3:// or https:// address of a ``.tifxyz`` folder, or of a segment folder
    (``<scroll>/segments/<id>/``) whose ``mesh/`` holds one.
    """
    https = to_https(url).rstrip("/") + "/"
    if not https.startswith(BUCKET_HTTPS):
        raise ValueError(f"{url}: not in the open-data bucket")
    key = https[len(BUCKET_HTTPS) + 1:]
    if not key.rstrip("/").endswith(".tifxyz"):
        found = [p for p in list_prefixes(key + "mesh/") if p.rstrip("/").endswith(".tifxyz")]
        found = found or [p for p in list_prefixes(key) if p.rstrip("/").endswith(".tifxyz")]
        if not found:
            raise FileNotFoundError(f"{url}: no .tifxyz folder found")
        key = found[0]
    dst = default_cache_dir() / "segments" / key.rstrip("/")
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("x.tif", "y.tif", "z.tif", "meta.json"):
        p = dst / f
        if not p.exists():
            raw = _get(f"{BUCKET_HTTPS}/{key}{f}")
            if raw is None:
                if f == "meta.json":
                    continue
                raise FileNotFoundError(f"{BUCKET_HTTPS}/{key}{f}")
            p.write_bytes(raw)
    return dst


def load_surface(src: str) -> Surface:
    if re.match(r"^(s3|https?)://", src):
        folder = fetch_segment(src)
        s = read_tifxyz(folder)
        s.source = str(folder)
        m = re.search(r"segments/([^/]+)/(?:mesh/)?[^/]+\.tifxyz/?$", s.source)
        if m:
            s.name = m.group(1)
        return s
    p = Path(src)
    if p.suffix.lower() == ".obj":
        return read_obj(p)
    if p.is_dir() and not (p / "x.tif").exists():  # a VC3D paths/<segment>/ folder, or a segment folder
        inner = sorted(p.glob("*.tifxyz")) + sorted(p.glob("mesh/*.tifxyz"))
        if inner:
            p = inner[0]
    return read_tifxyz(p)


def infer_volume(surface: Surface, catalog: Catalog, scroll: str | None = None, volume: str | None = None) -> Volume:
    """Work out which scan the segment was traced on, from the arguments, its path or its meta.json."""
    text = f"{surface.source} {surface.name}"
    if scroll is None:
        known = set(catalog.scrolls())
        scroll = next((c for c in re.findall(r"PHerc[0-9A-Za-z]+", text) if c in known), None)
        if scroll is None:
            raise ValueError("cannot tell which scroll this segment is from: pass --scroll (e.g. PHerc0800)")
    if volume is None:
        tv = str(surface.meta.get("target_volume", ""))
        m = re.match(r"(\d{14})", tv) or re.search(r"-on-(\d{14})", text)
        if m:
            volume = m.group(1)
    if volume is None:
        with_pred = [v for v in catalog.volumes(scroll) if catalog.volume(scroll, v).surface]
        if len(with_pred) != 1:
            raise ValueError(f"cannot tell which volume of {scroll} this segment was traced on: pass --volume "
                             f"(volumes with a surface prediction: {', '.join(with_pred) or 'none'})")
        volume = with_pred[0]
    return catalog.volume(scroll, volume)


def spread_nodes(surface: Surface, n: int = 12) -> np.ndarray:
    """Indices of up to ``n`` nodes spread evenly over the surface (farthest-point sampling in map
    coordinates, starting from the node nearest the middle)."""
    pts = surface.uv
    if len(pts) == 0:
        return np.zeros(0, int)
    chosen = [int(np.argmin(((pts - pts.mean(0)) ** 2).sum(1)))]
    d = ((pts - pts[chosen[0]]) ** 2).sum(1)
    while len(chosen) < min(n, len(pts)):
        i = int(np.argmax(d))
        chosen.append(i)
        d = np.minimum(d, ((pts - pts[i]) ** 2).sum(1))
    return np.array(chosen, int)


def check_segment(surface: Surface, vol: Volume, cal: Calibration, n_points: int = 12, workers: int = 4,
                  log=None) -> dict:
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.63)
    idx = spread_nodes(surface, n_points)
    pts = [[int(round(c)) for c in surface.zyx[i]] for i in idx]
    feats = features_at_many(vol, pts, workers, log=log)
    rows = []
    for i, f in zip(idx, feats):
        s = cal.score(f["features"])
        rows.append({"zyx": f["zyx"], "xyz": f["zyx"][::-1], "uv": surface.uv[i].tolist(), "score": s,
                     "features": f["features"]})
    scores = np.array([r["score"] for r in rows], float)
    ok = np.isfinite(scores)
    med = float(np.median(scores[ok])) if ok.any() else float("nan")
    summary = {
        "segment": surface.name, "scroll": vol.scroll, "volume": vol.volume, "voxel_um": vol.voxel_um,
        "n_nodes": int(len(surface.zyx)), "area_cm2": surface.area_cm2, "n_points": int(ok.sum()),
        "median_score": med, "frac_clean": float(np.mean(scores[ok] > thr)) if ok.any() else float("nan"),
        "threshold": thr,
        "verdict": "unknown (no scorable points)" if not ok.any() else FOLLOWS if med > thr else CROSSES,
        "rule": f"follows the sheet when the median point scores above {thr:.2f}",
        "trouble_spots": [r["xyz"] for r in sorted(rows, key=lambda r: np.nan_to_num(r["score"], nan=np.inf))
                          if r["score"] < 0 and not no_papyrus(r)],
        "no_papyrus": [r["xyz"] for r in rows if no_papyrus(r)],
        "validated_scan": validated_scan(vol),
        "errors": sorted({r["features"]["error"] for r in rows if "error" in r["features"]}),
    }
    return {"summary": summary, "points": rows}


def no_papyrus(row: dict) -> bool:
    """The CT around this point is (almost) empty: the segment has left the scroll's papyrus or the scan."""
    return bool(row["features"].get("ct_valid", 1.0) < NO_PAPYRUS) if "features" in row else False


def node_scores(surface: Surface, result: dict) -> np.ndarray:
    """Each node takes the score of its nearest sample point (in map coordinates)."""
    uv = np.array([p["uv"] for p in result["points"]], float)
    sc = np.array([p["score"] for p in result["points"]], float)
    keep = np.isfinite(sc)
    uv, sc = uv[keep], sc[keep]
    if not len(sc):
        return np.full(len(surface.uv), np.nan)
    out = np.empty(len(surface.uv))
    for a in range(0, len(surface.uv), 50000):
        b = surface.uv[a:a + 50000]
        out[a:a + 50000] = sc[np.argmin(((b[:, None, :] - uv[None]) ** 2).sum(2), 1)]
    return out


def plot_check(surface: Surface, result: dict, path) -> None:
    """Map of the segment, each region coloured by the score of its nearest sample point."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    s = result["summary"]
    ns = node_scores(surface, result)
    norm = TwoSlopeNorm(vmin=-2.5, vcenter=0.0, vmax=2.0)
    cmap = plt.get_cmap("RdBu")
    fig, ax = plt.subplots(figsize=(6.4, 6.4 * 0.86), dpi=130)
    if surface.grid_shape:
        img = np.full(surface.grid_shape, np.nan)
        rr, cc = surface.uv[:, 0].astype(int), surface.uv[:, 1].astype(int)
        img[rr, cc] = ns
        im = ax.imshow(img, cmap=cmap, norm=norm, interpolation="nearest")
        pu = [(p["uv"][1], p["uv"][0]) for p in result["points"]]
    else:
        im = ax.scatter(surface.uv[:, 1], surface.uv[:, 0], c=ns, cmap=cmap, norm=norm, s=2, lw=0)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        pu = [(p["uv"][1], p["uv"][0]) for p in result["points"]]
    for (u, v), p in zip(pu, result["points"]):
        if no_papyrus(p):
            ax.plot(u, v, "x", ms=7, mec="black", mew=1.6)
        elif np.isfinite(p["score"]):
            ax.plot(u, v, "o", ms=5, mfc="white", mec="black", mew=0.8)
            ax.annotate(f"{p['score']:+.1f}", (u, v), xytext=(4, 4), textcoords="offset points", fontsize=7)
    ax.margins(0.06)
    if surface.grid_shape:
        h, w = surface.grid_shape
        ax.set_xlim(-0.06 * w, 1.06 * w)
        ax.set_ylim(1.06 * h, -0.06 * h)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("scout score (blue = clean papyrus, red = crushed)", fontsize=8)
    cb.ax.axhline(s["threshold"], color="black", lw=1)
    extra = f"; x = no papyrus in the CT ({len(s['no_papyrus'])})" if s.get("no_papyrus") else ""
    ax.set_title(f"{s['segment'][:48]}\n{s['verdict']}: median score {s['median_score']:+.2f}, "
                 f"{s['frac_clean']:.0%} of points clean{extra}", fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def to_point_collections(result: dict) -> dict:
    """The sample points as colour-coded VC3D point collections (same colours as the scan export)."""
    from .vc3d import collections_doc, GREEN, RED, YELLOW

    s = result["summary"]
    thr = s["threshold"]
    pts = [p for p in result["points"] if np.isfinite(p["score"])]
    name = f"check {s['segment'][:40]}"
    return collections_doc([
        (f"{name}: clean (score > {thr:.2f})", GREEN, [p for p in pts if p["score"] > thr]),
        (f"{name}: middling (0 to {thr:.2f})", YELLOW, [p for p in pts if 0 <= p["score"] <= thr]),
        (f"{name}: crushed (score < 0)", RED, [p for p in pts if p["score"] < 0]),
    ])
