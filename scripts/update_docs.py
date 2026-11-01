"""Regenerate the data-driven parts of the docs: the README's atlas section, the atlas paragraph of
SUBMISSION.md and the VC3D exports.

    python -I scripts/update_docs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrollscout.atlas import inner_seeds  # noqa: E402
from scrollscout.scout import Calibration  # noqa: E402
from scrollscout.vc3d import to_point_collections  # noqa: E402


def name(scroll: str) -> str:
    return re.sub(r"^PHerc0*", "PHerc. ", scroll)


def load():
    items = [json.loads(f.read_text()) for f in sorted((ROOT / "atlas").glob("PHerc*.json"))]
    items.sort(key=lambda d: -d["summary"]["score_p90"])
    dense = {f.stem: json.loads(f.read_text()) for f in sorted((ROOT / "atlas_dense").glob("PHerc*.json"))}
    return items, dense


def stability() -> dict | None:
    f = ROOT / "results" / "atlas_stability.json"
    return json.loads(f.read_text()) if f.exists() else None


def short_list(keys) -> str:
    """PHerc. 175A, 125, 483A and 306B"""
    names = [name(k) for k in keys]
    if not names:
        return ""
    names = names[:1] + [n[len("PHerc. "):] for n in names[1:]]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def total_points(items, dense) -> int:
    per = {d["summary"]["scroll"]: d["summary"]["n_points"] for d in items}
    return sum(per.values()) + sum(d["summary"]["n_points"] - per.get(k, 0) for k, d in dense.items())


def atlas_section(items, dense) -> str:
    per = items[0]["summary"]["n_points"]
    n = total_points(items, dense)
    mins = sum(d["summary"].get("secs", 0) for d in items) / len(items) / 60
    st = stability()
    dense_line = (f", plus {short_list(dense)} scanned at {max(d['summary']['n_points'] for d in dense.values())} "
                  f"points each for their seeds" if dense else "")
    stab_line = (f"\nThe ranking hardly depends on which points were drawn: an earlier pass with 64 different points "
                 f"per scroll (and the v0.1 feature code) ranks the scrolls almost the same way (Spearman "
                 f"{st['frac_clean']:.2f} on the share of clean points, {st['score_p90']:.2f} on the best 10%)."
                 if st else "")
    clean = sorted(items, key=lambda d: -d["summary"]["frac_clean"])
    worst = sorted(items, key=lambda d: d["summary"]["frac_clean"])[:5]
    lead116 = [d for d in items if abs(d["summary"]["voxel_um"] - 8.64) < 0.05][:3]
    rows = []
    for i, d in enumerate(items[:8], 1):
        s = d["summary"]
        src = dense.get(s["scroll"], d)
        b = inner_seeds(src["points"])[0]
        z, y, x = b["zyx"]
        rows.append(f"| {i} | {name(s['scroll'])} | {s['voxel_um']:.2f} µm / {s['energy_kev']:.0f} keV | "
                    f"{s['frac_clean']:.0%} | {s['score_p90']:.2f} | {x}, {y}, {z} | {src['summary']['n_points']} |")
    table_rows = "\n".join(rows)
    detail = "\n\n".join(f"![{name(k)} cross-sections](figures/fig_detail_{k}.png)" for k in dense)
    return f"""<!-- ATLAS:START -->
{n:,} sample points: {per} spread through each of the {len(items)} eligible volumes (8 heights × 4 distances
from the axis){dense_line}. About {mins:.1f} minutes per scroll on 4 CPU cores.{stab_line}

![Ranking](figures/fig_atlas_ranking.png)

- **Cleanest:** {name(clean[0]['summary']['scroll'])} ({clean[0]['summary']['frac_clean']:.0%} of points clean), {', '.join(f"{name(d['summary']['scroll'])[7:]} ({d['summary']['frac_clean']:.0%})" for d in clean[1:4])}.
- **Most crushed:** {', '.join(f"{name(d['summary']['scroll'])} ({d['summary']['frac_clean']:.0%})" for d in worst)}.
  Automatic tracing will struggle almost everywhere in these.
- **On the 116 keV protocol** of the two scrolls where text has turned up, {', '.join(name(d['summary']['scroll']) for d in lead116)} lead.

Top eight, with each scroll's best seed in its inner zone (within 0.45 of the way from the axis to the
outside and away from the top and bottom 15%, where both known text finds lie):

| rank | scroll | scan | share of points clean | best 10% score | best inner seed (x, y, z) | points behind the seed |
|---:|---|---|---:|---:|---|---:|
{table_rows}

![Inside each scroll](figures/fig_atlas_maps.png)

Cross-sections through the best inner seeds of the densely scanned scrolls (blue = clean, red =
crushed, white ring = seed):

{detail}

All 21 scrolls: [`atlas/SUMMARY.md`](atlas/SUMMARY.md). Every seed (5 overall and 3 inner per scroll):
[`atlas/seeds.csv`](atlas/seeds.csv). Every sample point with all its features: `atlas/<scroll>.json`.
VC3D point collections for every scroll (clean, middling and crushed points, and seeds):
`atlas/vc3d/<scroll>.vc3d_points.json`.
<!-- ATLAS:END -->"""


def census_section() -> str:
    f = ROOT / "results" / "segment_census.json"
    if not f.exists():
        return "<!-- CENSUS:START -->\n<!-- CENSUS:END -->"
    rows = [r for r in json.loads(f.read_text())["segments"]
            if r["median_score"] is not None and r["median_score"] == r["median_score"]]
    follows = [r for r in rows if r["verdict"].endswith("follows the sheet")]
    scrolls = sorted({r["scroll"] for r in rows}, key=lambda s: -sum(r["scroll"] == s for r in rows))
    table = "\n".join(
        f"| {name(s)} | {sum(r['scroll'] == s for r in rows)} | {sum(r['scroll'] == s for r in follows)} |"
        for s in scrolls)
    judged = [r for r in rows if r.get("survey_verdict")]
    big = [s for s in scrolls if sum(r["scroll"] == s for r in rows) >= 5]
    worst_txt = ""
    if big:
        worst = min(big, key=lambda s: sum(r["scroll"] == s for r in follows) / sum(r["scroll"] == s for r in rows))
        n_w = sum(r["scroll"] == worst for r in rows)
        f_w = sum(r["scroll"] == worst for r in follows)
        if f_w / n_w < 0.25:
            worst_txt = (f" {name(worst)} stands out: {n_w - f_w} of its {n_w} segments run through papyrus the score "
                         f"rates as crushed.")
    skipped = json.loads(f.read_text()).get("skipped", [])
    skip_txt = ""
    if skipped:
        skip_scrolls = ", ".join(sorted({name(r["scroll"]) for r in skipped}))
        skip_um = ", ".join(sorted({f"{r['voxel_um']:g}" for r in skipped}))
        skip_txt = (f" The {len(skipped)} segments of {skip_scrolls} were not checked: they sit on a {skip_um} µm "
                    f"scan, outside the 8.64–9.36 µm scans the score was validated on.")
    return f"""<!-- CENSUS:START -->
### Every published segment, checked

`check-segment` ran on every segment in the open-data bucket it can check: the {len(rows)} segments, on
{len(scrolls)} scrolls, with a tifxyz mesh traced on an 8.6–9.4 µm scan that has a published surface prediction
(`scripts/census_segments.py`). **{len(follows)} of {len(rows)}** likely follow their sheet. {len(judged)} of them were
also judged by eye in the survey (test 2); for the rest the verdicts are predictions, useful for deciding
which segments to run ink detection on, or to train on, first.{worst_txt}{skip_txt}

| scroll | segments checked | likely follow the sheet |
|---|---:|---:|
{table}

![Census](figures/fig_census.png)

Every segment's verdict, median score, share of clean points and survey verdict:
[`census/SEGMENTS.md`](census/SEGMENTS.md) (also as [`census/segments.csv`](census/segments.csv)).
<!-- CENSUS:END -->"""


def meshes_section() -> str:
    f = ROOT / "results" / "survey_meshes.json"
    s = json.loads(f.read_text()).get("summary") if f.exists() else None
    if not s:
        return "<!-- MESHES:START -->\n<!-- MESHES:END -->"
    return f"""<!-- MESHES:START -->
Scoring each patch over its whole surface with `check-segment` (12 points spread over the patch instead of
the seed alone) gives AUC {s['auc']:.2f} ({s['ci'][0]:.2f}–{s['ci'][1]:.2f}) on the same {s['n']} patches. The score was tuned on
these patches, so this checks consistency rather than adding an independent test. The fixed rule is strict on
patches this large (about 12 cm² each): of the {s['n_flagged_follows']} it passes, {s['rule_precision']:.0%} stayed on the sheet
(base rate {s['base_rate']:.0%}), and it rejects {s['rule_specificity']:.0%} of the patches that did not, but it passes only
{s['rule_sensitivity']:.0%} of the good ones.
<!-- MESHES:END -->"""


def submission_atlas(items, dense) -> str:
    by_clean = sorted(items, key=lambda d: -d["summary"]["frac_clean"])
    cleanest = ", ".join(name(d["summary"]["scroll"]) for d in by_clean[:3])
    crushed = ", ".join(name(d["summary"]["scroll"]) for d in by_clean[::-1][:3])
    st = stability()
    stab = (f" The ranking barely moves between two passes over different points (Spearman {st['frac_clean']:.2f})."
            if st else "")
    dense_txt = (f" {short_list(dense)}, the most promising, were scanned at "
                 f"{max(d['summary']['n_points'] for d in dense.values())} points each." if dense else "")
    return (f"<!-- ATLAS_LINE -->{total_points(items, dense):,} points scored over all {len(items)} First Letters "
            f"volumes. Cleanest: {cleanest}; most crushed: {crushed}, where automatic tracing will struggle almost "
            f"everywhere.{dense_txt}{stab} Every scroll gets seeds (5 overall, 3 in the inner zone where both known "
            f"text finds lie) with ready-to-run fls.py commands, and a VC3D point-collections file.<!-- /ATLAS_LINE -->")


def submission_census() -> str:
    f = ROOT / "results" / "segment_census.json"
    if not f.exists():
        return "<!-- CENSUS_LINE --><!-- /CENSUS_LINE -->"
    rows = [r for r in json.loads(f.read_text())["segments"]
            if r["median_score"] is not None and r["median_score"] == r["median_score"]]
    fol = sum(r["verdict"].endswith("follows the sheet") for r in rows)
    k = len({r["scroll"] for r in rows})
    return (f"<!-- CENSUS_LINE -->`check-segment` on every published segment it can check ({len(rows)} segments on {k} "
            f"scrolls, all on 8.6–9.4 µm scans): {fol} likely follow their sheet. The list (census/SEGMENTS.md, census/segments.csv) says which "
            f"segments are worth ink detection or training first.<!-- /CENSUS_LINE -->")


def main():
    items, dense = load()
    readme = ROOT / "README.md"
    t = readme.read_text()
    new = atlas_section(items, dense)
    if "<!-- ATLAS:START -->" in t:
        t = re.sub(r"<!-- ATLAS:START -->.*?<!-- ATLAS:END -->", lambda m: new, t, flags=re.S)
    else:
        head = "## The atlas: all 21 scrolls still eligible for First Letters\n\n"
        a = t.index(head) + len(head)
        b = t.index("## Quick start")
        t = t[:a] + new + "\n\n" + t[b:]
    t = re.sub(r"<!-- CENSUS:START -->.*?<!-- CENSUS:END -->", lambda m: census_section(), t, flags=re.S)
    t = re.sub(r"<!-- MESHES:START -->.*?<!-- MESHES:END -->", lambda m: meshes_section(), t, flags=re.S)
    readme.write_text(t)
    sub = ROOT / "SUBMISSION.md"
    if sub.exists():
        s = sub.read_text()
        s = re.sub(r"<!-- ATLAS_LINE -->(.*?<!-- /ATLAS_LINE -->)?", lambda m: submission_atlas(items, dense), s,
                   count=1, flags=re.S)
        s = re.sub(r"<!-- CENSUS_LINE -->.*?<!-- /CENSUS_LINE -->", lambda m: submission_census(), s, count=1, flags=re.S)
        sub.write_text(s)
    cal = Calibration.load(ROOT / "results" / "calibration.json")
    thr = cal.stats["_good_threshold"]["value"]
    out = ROOT / "atlas" / "vc3d"
    out.mkdir(parents=True, exist_ok=True)
    for d in items:
        src = dense.get(d["summary"]["scroll"], d)
        (out / f"{d['summary']['scroll']}.vc3d_points.json").write_text(json.dumps(to_point_collections(src, thr)))
    print(f"README atlas section updated; {len(items)} VC3D exports in {out}")


if __name__ == "__main__":
    main()
