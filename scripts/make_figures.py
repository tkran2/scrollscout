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
from scrollscout.score import combined_score  # noqa: E402
from scrollscout.stats import auc  # noqa: E402

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
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    style()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_validation(Path(a.results), out)
    fig_examples(Path(a.results), out)
    fig_text_regions(Path(a.results), out)
    fig_atlas(Path(a.atlas), out)
    print("figures in", out)


if __name__ == "__main__":
    main()
