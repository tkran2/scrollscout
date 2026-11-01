"""Figures for the README and the report.

    python -I scripts/make_figures.py --results results --atlas atlas --out figures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.atlas import inner_seeds  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
ORDINAL = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # blue 250/400/550/700
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
LABELS = ["swirls / left\nthe papyrus", "on the sheet\nin parts", "on the sheet\nover most", "on the sheet\nthroughout"]


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.titlecolor": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
    })


def roc_points(score, positive):
    order = np.argsort(-score)
    y = positive[order]
    tp = np.concatenate([[0], np.cumsum(y)]) / max(1, y.sum())
    fp = np.concatenate([[0], np.cumsum(~y)]) / max(1, (~y).sum())
    return fp, tp


def fig_validation(results: Path, out: Path):
    rows = json.loads((results / "survey_features.json").read_text())
    an = json.loads((results / "survey_analysis.json").read_text())
    cv = json.loads((results / "crossval.json").read_text())
    label = np.array([r["label"] for r in rows])
    good = label >= 2
    # honest scores: each scroll scored by a model chosen on the other scrolls only
    score = np.array(cv["held_out_scores"], float)
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw={"width_ratios": [1, 1.25, 1.25]})

    ax = axs[0]
    fp, tp = roc_points(score, good)
    ax.plot([0, 1], [0, 1], color=INK2, lw=1, ls=(0, (4, 4)))
    ax.plot(fp, tp, color=BLUE, lw=2)
    ax.set_title(f"Scout score finds the good seeds\nheld-out AUC {cv['auc']:.2f} (95% CI {cv['ci'][0]:.2f}–{cv['ci'][1]:.2f}), "
                 f"leave-one-scroll-out")
    ax.set_xlabel("share of bad seeds flagged as good")
    ax.set_ylabel("share of good seeds found")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_aspect("equal")

    ax = axs[1]
    rng = np.random.default_rng(0)
    for k in range(4):
        s = score[label == k]
        ax.scatter(k + rng.uniform(-0.18, 0.18, s.size), s, s=46, color=ORDINAL[k], edgecolor=SURFACE, linewidth=1.5, zorder=3)
        if s.size:
            ax.hlines(np.median(s), k - 0.28, k + 0.28, color=INK, lw=2, zorder=4)
    ax.set_xticks(range(4))
    ax.set_xticklabels(LABELS, fontsize=9)
    ax.set_ylabel("held-out scout score at the seed")
    ax.set_title("Score vs. what the patch actually did\n(65 patches judged by eye in the First Letters survey; line = median)")
    ax.grid(axis="x", visible=False)

    ax = axs[2]
    feats = an["features"]
    from scrollscout.score import SCORE_TERMS_SIGNED

    names = [k for k, _ in SCORE_TERMS_SIGNED if k in feats and np.isfinite(feats[k]["auc"])]
    vals = np.array([max(feats[k]["auc"], 1 - feats[k]["auc"]) for k in names])
    order = np.argsort(vals)
    names = [names[i] for i in order]
    vals = vals[order]
    lo = np.array([feats[k]["ci"][0] if feats[k]["auc"] >= 0.5 else 1 - feats[k]["ci"][1] for k in names])
    hi = np.array([feats[k]["ci"][1] if feats[k]["auc"] >= 0.5 else 1 - feats[k]["ci"][0] for k in names])
    yy = np.arange(len(names))
    ax.barh(yy, vals - 0.5, left=0.5, color=BLUE, height=0.62)
    ax.errorbar(vals, yy, xerr=[vals - lo, hi - vals], fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
    nice = {"pred_planarity": "prediction: sheets flat", "pred_dispersion": "prediction: no swirl",
            "pred_thick": "prediction: sheets not fused", "pred_bigcc": "prediction: sheets continuous",
            "pred_frac": "prediction: sheet density", "pred_ncomp_per_kvox": "prediction: few fragments",
            "ct_planarity": "CT: layered texture", "ct_dispersion": "CT: no swirl", "ct_contrast": "CT: sheet/gap contrast",
            "ct_valid": "CT: inside papyrus"}
    ax.set_yticks(yy)
    ax.set_yticklabels([nice.get(n, n) for n in names], fontsize=9)
    ax.axvline(0.5, color=INK2, lw=1)
    ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("AUC (0.5 = no better than chance)")
    ax.set_title("The five signals in the score, each on its own\n(bars: AUC; whiskers: 95% bootstrap CI)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig_validation.png", dpi=150)
    plt.close(fig)


def fig_text_regions(results: Path, out: Path):
    p = results / "text_regions.json"
    if not p.exists():
        return
    rep = json.loads(p.read_text())
    fig, axs = plt.subplots(1, len(rep), figsize=(5.2 * len(rep), 4.2), sharey=True)
    axs = np.atleast_1d(axs)
    titles = {"PHerc0343": "PHerc. 343: the 18 letters that won\nthe October First Letters prize",
              "PHerc1447": "PHerc. 1447: where the team found\ntext on September 24"}
    rng = np.random.default_rng(0)
    for ax, (scroll, r) in zip(axs, rep.items()):
        rs = np.array(r["random_scores"], float)
        ts = np.array([v for v in r["text_scores"] if v is not None and np.isfinite(v)], float)
        ax.scatter(rng.uniform(-0.2, 0.2, rs.size), rs, s=40, color=BLUE, edgecolor=SURFACE, linewidth=1.5, label="random points in the scroll", zorder=3)
        ax.scatter(1 + rng.uniform(-0.2, 0.2, ts.size), ts, s=40, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, label="where text was found", zorder=3)
        for x, s in ((0, rs), (1, ts)):
            ax.hlines(np.median(s), x - 0.3, x + 0.3, color=INK, lw=2, zorder=4)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["random points\nin the scroll", "where text\nwas found"])
        ax.set_title(f"{titles.get(scroll, scroll)}\ntext median beats {r['percentile_of_text_median']:.0f}% of random points")
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("scout score")
    fig.tight_layout()
    fig.savefig(out / "fig_text_regions.png", dpi=150)
    plt.close(fig)


def fig_team_segments(results: Path, out: Path):
    p = results / "team_segments.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    groups = [("PHerc. 800\nfollows the sheet", lambda r: r["scroll"] == "PHerc0800" and r["label"] == 1, BLUE),
              ("PHerc. 1447\nfollows the sheet", lambda r: r["scroll"] == "PHerc1447" and r["label"] == 1, BLUE),
              ("PHerc. 1447\ncuts across layers", lambda r: r["scroll"] == "PHerc1447" and r["label"] == 0, ORANGE)]
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    rng = np.random.default_rng(0)
    for i, (name, sel, col) in enumerate(groups):
        segs = [r for r in d["segments"] if sel(r)]
        for r in segs:
            s = np.array([v for v in r["scores"] if v is not None and np.isfinite(v)])
            ax.scatter(i + rng.uniform(-0.28, 0.28, s.size), s, s=9, color=col, alpha=0.25, edgecolor="none", zorder=2)
        med = np.array([r["median"] for r in segs])
        ax.scatter(i + rng.uniform(-0.12, 0.12, med.size), med, s=70, color=col, edgecolor=SURFACE, linewidth=1.6, zorder=4)
        ax.text(i, 1.75, f"{len(segs)} segments", ha="center", color=INK2, fontsize=9)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([g[0] for g in groups])
    ax.set_ylabel("scout score")
    ax.set_ylim(-3.6, 2.0)
    s = d["summary"]
    ax.set_title(f"The team's own segments, on two scrolls never used to build the score:\n"
                 f"all {s['n_good']} that follow the sheet score above all {s['n_bad']} that cut across layers "
                 f"(AUC {s['auc']:.2f}, p = {s['p']:.4f})\nbig dots: segment medians; small dots: points on each segment",
                 fontsize=10.5)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig_team_segments.png", dpi=150)
    plt.close(fig)


def fig_segment_check(results: Path, out: Path):
    """check-segment's maps of a good and a typical bad team segment from the same scroll."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    from scrollscout.segment import load_surface, no_papyrus, node_scores

    p = results / "team_segments.json"
    if not p.exists():
        return
    segs = [r for r in json.loads(p.read_text())["segments"] if r["scroll"] == "PHerc1447" and r["label"] is not None]
    if not segs or "uv" not in segs[0]["points"][0]:
        return
    good = max((r for r in segs if r["label"] == 1), key=lambda r: r["median"])
    bad = sorted((r for r in segs if r["label"] == 0), key=lambda r: r["median"])
    bad = bad[len(bad) // 2]  # a typical one, not the worst
    div = LinearSegmentedColormap.from_list("div", ["#e34948", "#f3b8b1", "#f0efec", "#9ec5f4", "#1c5cab"])
    norm = TwoSlopeNorm(0.0, -2.5, 1.5)
    fig, axs = plt.subplots(1, 2, figsize=(12.4, 5.6))
    for ax, r, survey in zip(axs, (good, bad), ("follows the sheet", "cuts across several layers")):
        surf = load_surface(f"s3://vesuvius-challenge-open-data/{r['scroll']}/segments/{r['segment']}/")
        res = {"points": r["points"]}
        img = np.full(surf.grid_shape, np.nan)
        img[surf.uv[:, 0].astype(int), surf.uv[:, 1].astype(int)] = node_scores(surf, res)
        im = ax.imshow(img, cmap=div, norm=norm, interpolation="nearest")
        for q in r["points"]:
            if no_papyrus(q):
                ax.scatter([q["uv"][1]], [q["uv"][0]], s=46, marker="x", color=INK, linewidth=1.6, zorder=3)
            elif q["score"] is not None and np.isfinite(q["score"]):
                ax.scatter([q["uv"][1]], [q["uv"][0]], s=34, color="white", edgecolor=INK, linewidth=0.9, zorder=3)
        h, w = surf.grid_shape
        ax.set_xlim(-0.04 * w, 1.04 * w)
        ax.set_ylim(1.04 * h, -0.04 * h)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(f"survey: {survey}\nscout: {r['tool_verdict']} (median {r['median']:+.2f}, "
                     f"{r['frac_clean']:.0%} of points clean)", fontsize=10, fontweight="normal")
    fig.suptitle("check-segment on two of the team's PHerc. 1447 segments: each region takes the score of its "
                 "nearest scored point (dots; x = no papyrus in the CT)", x=0.01, y=1.06, ha="left", fontweight="bold",
                 fontsize=11)
    cb = fig.colorbar(im, ax=axs.tolist(), shrink=0.75, pad=0.01)
    cb.set_label("scout score (blue = clean papyrus, red = crushed)", color=INK2)
    fig.savefig(out / "fig_segment_check.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_census(results: Path, out: Path):
    """check-segment's verdicts on every published segment that can be checked, per scroll."""
    p = results / "segment_census.json"
    if not p.exists():
        return
    rows = [r for r in json.loads(p.read_text())["segments"] if r["median_score"] is not None
            and np.isfinite(r["median_score"])]
    if not rows:
        return
    scrolls = sorted({r["scroll"] for r in rows}, key=lambda s: -sum(r["scroll"] == s for r in rows))
    follow = np.array([sum(r["scroll"] == s and r["verdict"].endswith("follows the sheet") for r in rows) for s in scrolls])
    total = np.array([sum(r["scroll"] == s for r in rows) for s in scrolls])
    fig, ax = plt.subplots(figsize=(9.6, 0.55 * len(scrolls) + 1.6))
    y = np.arange(len(scrolls))[::-1]
    ax.barh(y, follow, color=BLUE, height=0.62, label="likely follows the sheet")
    ax.barh(y, total - follow, left=follow, color=ORANGE, height=0.62, label="likely cuts across layers")
    for yi, f, n in zip(y, follow, total):
        ax.text(n + 0.6, yi, f"{f} of {n}", va="center", color=INK2, fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels([s.replace("PHerc", "PHerc. ").replace(". 0", ". ") for s in scrolls])
    ax.set_xlabel("published segments")
    ax.set_xlim(0, total.max() * 1.15)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title(f"check-segment on all {len(rows)} published segments it can check: "
                 f"{follow.sum()} likely follow their sheet", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(out / "fig_census.png", dpi=150)
    plt.close(fig)


def fig_scroll_details(dense: Path, out: Path):
    """Cross-sections of the densely scanned scrolls, with every nearby sample point coloured by score."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    from scrollscout.atlas import inner_seeds
    from scrollscout.sampling import load_coarse

    files = sorted(dense.glob("PHerc*.json"))
    if not files:
        return
    div = LinearSegmentedColormap.from_list("div", ["#e34948", "#f3b8b1", "#f0efec", "#9ec5f4", "#1c5cab"])
    for f in files:
        d = json.loads(f.read_text())
        s = d["summary"]
        cs = load_coarse(s["ct"])
        fac = cs.factor
        pts = [p for p in d["points"] if np.isfinite(p["score"])]
        seeds = inner_seeds(pts, k=3)
        zs = [int(sd["zyx"][0] / fac) for sd in seeds] or [int(np.mean(cs.z_extent))]
        band = max(6, int(0.06 * (cs.z_extent[1] - cs.z_extent[0])))
        fig, axs = plt.subplots(1, len(zs), figsize=(5.0 * len(zs), 5.4))
        axs = np.atleast_1d(axs)
        for ax, zc, sd in zip(axs, zs, seeds or [None] * len(zs)):
            ax.imshow(cs.vol[zc], cmap="gray", vmin=0, vmax=np.percentile(cs.vol[cs.vol > 0], 99.5))
            near = [p for p in pts if abs(p["zyx"][0] / fac - zc) <= band]
            if near:
                yy = np.array([p["zyx"][1] / fac for p in near])
                xx = np.array([p["zyx"][2] / fac for p in near])
                sc = np.array([p["score"] for p in near])
                im = ax.scatter(xx, yy, c=sc, cmap=div, norm=TwoSlopeNorm(0.0, -2.0, 1.5), s=46,
                                edgecolor="white", linewidth=0.8, zorder=3)
            if sd:
                ax.scatter([sd["zyx"][2] / fac], [sd["zyx"][1] / fac], s=260, facecolor="none", edgecolor="white",
                           linewidth=2.2, zorder=4)
                x, y, z = sd["zyx"][2], sd["zyx"][1], sd["zyx"][0]
                ax.set_title(f"z = {z} (±{band * fac} voxels shown)\nwhite ring: seed x {x}, y {y}, z {z}", fontsize=9.5,
                             loc="left")
            m = cs.mask[zc]
            if m.any():
                rr, cc = np.nonzero(m)
                pad = 6
                ax.set_xlim(max(0, cc.min() - pad), min(m.shape[1], cc.max() + pad))
                ax.set_ylim(min(m.shape[0], rr.max() + pad), max(0, rr.min() - pad))
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
        fig.canvas.draw()  # put the title just above the panels' own titles, not at the top of the canvas
        inv = fig.transFigure.inverted()
        top = max(inv.transform(ax.get_tightbbox(fig.canvas.get_renderer()).corners())[:, 1].max() for ax in axs)
        fig.suptitle(f"{s['scroll'].replace('PHerc', 'PHerc. ').replace('. 0', '. ')}: cross-sections through its best inner "
                     f"seeds ({s['n_points']} points scored; blue = clean, red = crushed)",
                     x=0.01, y=top + 0.03, ha="left", va="bottom", fontweight="bold", fontsize=11)
        cb = fig.colorbar(im, ax=axs.tolist(), shrink=0.7, pad=0.01)
        cb.set_label("scout score", color=INK2)
        fig.savefig(out / f"fig_detail_{s['scroll']}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)


def load_atlas(atlas: Path):
    items = []
    for f in sorted(atlas.glob("PHerc*.json")):
        items.append(json.loads(f.read_text()))
    return items


def fig_atlas(atlas: Path, out: Path):
    items = load_atlas(atlas)
    if not items:
        return
    items.sort(key=lambda d: -d["summary"]["score_p90"])
    # ranking
    fig, ax = plt.subplots(figsize=(8.5, 0.32 * len(items) + 1.4))
    names = [d["summary"]["scroll"].replace("PHerc", "PHerc. ").replace(". 0", ". ") for d in items]
    p90 = np.array([d["summary"]["score_p90"] for d in items])
    med = np.array([d["summary"]["score_median"] for d in items])
    is116 = np.array([abs(d["summary"]["voxel_um"] - 8.64) < 0.05 for d in items])
    yy = np.arange(len(items))[::-1]
    for y, a, b, c in zip(yy, med, p90, is116):
        col = BLUE if c else ORANGE
        ax.plot([a, b], [y, y], color=col, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([b], [y], s=64, color=col, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.scatter([a], [y], s=26, color=SURFACE, edgecolor=col, linewidth=1.5, zorder=3)
    ax.set_yticks(yy)
    ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlabel("scout score (open dot: median of the scroll's sample points; filled dot: best 10%)")
    ax.set_title("Where the papyrus is cleanest: the 21 scrolls still eligible for First Letters")
    from matplotlib.lines import Line2D

    ax.legend(handles=[Line2D([], [], color=BLUE, marker="o", lw=2, label="8.64 µm / 116 keV (same protocol as PHerc. 343 and 1447)"),
                       Line2D([], [], color=ORANGE, marker="o", lw=2, label="9.36 µm / 113 keV")],
              loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=2, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig_atlas_ranking.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # small multiples: where inside each scroll the clean papyrus is
    n = len(items)
    cols = 7
    rows_ = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows_, cols, figsize=(2.3 * cols, 2.5 * rows_ + 0.8), sharex=True, sharey=True)
    axs = axs.ravel()
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("blues", SEQ)
    allscores = np.concatenate([[p["score"] for p in d["points"] if np.isfinite(p["score"])] for d in items])
    vmin, vmax = np.percentile(allscores, [5, 95])
    for ax, d, name in zip(axs, items, names):
        pts = [p for p in d["points"] if np.isfinite(p["score"]) and np.isfinite(p["r_frac"])]
        r = np.array([p["r_frac"] for p in pts])
        z = np.array([p["z_frac"] for p in pts])
        s = np.array([p["score"] for p in pts])
        order = np.argsort(s)
        ax.scatter(r[order], z[order], c=s[order], cmap=cmap, vmin=vmin, vmax=vmax, s=18, edgecolor="none")
        ax.add_patch(plt.Rectangle((0, 0.15), 0.45, 0.70, fill=False, edgecolor=INK2, lw=0.8, ls=(0, (3, 3))))
        for sd in inner_seeds(d["points"])[:3]:
            ax.scatter([sd["r_frac"]], [sd["z_frac"]], s=90, facecolor="none", edgecolor=ORANGE, linewidth=1.6)
        ax.set_title(name, fontsize=9, loc="center")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(False)
    for ax in axs[n:]:
        ax.axis("off")
    fig.supxlabel("distance from the scroll's axis (0 = centre, 1 = outside)", color=INK2, fontsize=10)
    fig.supylabel("height in the scroll (0 = bottom, 1 = top)", color=INK2, fontsize=10)
    fig.suptitle("Inside each scroll: darker = cleaner papyrus; dashed box = inner zone where both known text finds lie; "
                 "orange rings = recommended inner seeds",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin, vmax))
    cb = fig.colorbar(sm, ax=axs.tolist(), shrink=0.6, pad=0.01)
    cb.set_label("scout score", color=INK2)
    fig.savefig(out / "fig_atlas_maps.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_examples(results: Path, out: Path, catalog_path: str | None = None):
    """Two seeds whose patches stayed on the sheet next to two that swirled, with their scores."""
    from scrollscout.catalog import Catalog
    from scrollscout.scout import Calibration
    from scrollscout.zarrhttp import ZArray

    rows = json.loads((results / "survey_features.json").read_text())
    cal = Calibration.load(results / "calibration.json")
    for r in rows:
        r["score"] = cal.score(r["features"])
    good = sorted((r for r in rows if r["label"] == 3), key=lambda r: -r["score"])[:2]
    bad = sorted((r for r in rows if r["label"] == 0 and r["features"].get("ct_valid", 0) > 0.9),
                 key=lambda r: r["score"])[:2]
    cat = Catalog.load(catalog_path)
    picks = good + bad
    fig, axs = plt.subplots(2, 4, figsize=(15, 7.6))
    for j, r in enumerate(picks):
        vol = cat.volume(r["scroll"], r["volume"])
        c = [v / 2 for v in r["seed_zyx"]]
        ct = ZArray.open(vol.ct, 1).read_centered(c, 96)
        pr = ZArray.open(vol.surface, 1).read_centered(c, 96)
        m = ct.shape[0] // 2
        verdict = "stayed on the sheet" if r["label"] >= 2 else "swirled"
        axs[0, j].imshow(ct[m], cmap="gray")
        axs[0, j].set_title(f"{r['scroll']} · patch {verdict}\nscout score {r['score']:+.2f}", fontsize=10,
                            color=INK, loc="left")
        axs[1, j].imshow(pr[m], cmap="gray")
        for ax in (axs[0, j], axs[1, j]):
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
    axs[0, 0].set_ylabel("CT (3.3 mm)", color=INK2)
    axs[1, 0].set_ylabel("published surface prediction", color=INK2)
    fig.suptitle("What the scout sees: clean seeds show thin, flat, separate sheets; crushed seeds show fused, swirling fragments",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "fig_examples.png", dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--atlas", default="atlas")
    ap.add_argument("--dense", default="atlas_dense")
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    style()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_validation(Path(a.results), out)
    fig_examples(Path(a.results), out)
    fig_text_regions(Path(a.results), out)
    fig_team_segments(Path(a.results), out)
    fig_segment_check(Path(a.results), out)
    fig_census(Path(a.results), out)
    fig_atlas(Path(a.atlas), out)
    fig_scroll_details(Path(a.dense), out)
    print("figures in", out)


if __name__ == "__main__":
    main()
