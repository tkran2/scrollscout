"""Build report/index.html: a one-page, self-contained summary of Scroll Scout's results.

    python -I scripts/make_report.py --results results --atlas atlas --figures figures --out report/index.html
"""

from __future__ import annotations

import argparse
import base64
import html
import re
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrollscout.atlas import inner_seeds  # noqa: E402

CSS = """
/* Layout: one reading column; figures break out to a wider frame; the atlas table scrolls inside its own box. */
:root {
  --bg: #f4f5f6; --surface: #fcfcfb; --fg: #16181b; --muted: #5b6168; --line: #d9dde1;
  --accent: #1f5fae; --accent-2: #b4541f; --code-bg: #eceef0;
  --display: "Spectral", "Iowan Old Style", Georgia, serif;
  --body: "Public Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111315; --surface: #1a1d20; --fg: #e8eaec; --muted: #a2a8ae; --line: #2c3135;
  --accent: #6ea8ee; --accent-2: #e8925e; --code-bg: #1f2326; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #111315; --surface: #1a1d20; --fg: #e8eaec; --muted: #a2a8ae; --line: #2c3135;
  --accent: #6ea8ee; --accent-2: #e8925e; --code-bg: #1f2326; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font: 16px/1.6 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
main { max-width: 860px; margin: 0 auto; padding-block: 48px 72px; display: grid; gap: 56px; }
header { display: grid; gap: 18px; }
.eyebrow { font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent-2); }
h1 { font: 600 clamp(2.2rem, 5vw, 3.4rem)/1.05 var(--display); margin: 0; text-wrap: balance; letter-spacing: -.01em; }
h2 { font: 600 1.7rem/1.2 var(--display); margin: 0 0 12px; text-wrap: balance; }
h3 { font: 600 1.05rem/1.3 var(--body); margin: 24px 0 8px; }
p { margin: 0 0 14px; max-width: 66ch; }
.lede { font-size: 1.15rem; color: var(--muted); max-width: 62ch; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 8px; }
.stat { border-top: 2px solid var(--fg); padding-top: 10px; }
.stat b { display: block; font: 600 1.9rem/1.1 var(--display); font-variant-numeric: tabular-nums; }
.stat span { font-size: .85rem; color: var(--muted); }
section { display: grid; gap: 6px; min-width: 0; }
figure { margin: 10px 0 6px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 10px; }
figure img { display: block; width: 100%; height: auto; border-radius: 3px; background: #fcfcfb; }
figcaption { font-size: .85rem; color: var(--muted); margin-top: 8px; }
.wide { margin-inline: calc(-1 * min(120px, max(0px, (100vw - 860px) / 2 - 24px))); }
table { border-collapse: collapse; width: 100%; font-size: .9rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font: 600 .75rem/1.2 var(--mono); letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
td.num, th.num { text-align: right; }
.scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font: 600 .72rem/1.6 var(--mono); }
.p116 { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
.p113 { background: color-mix(in srgb, var(--accent-2) 16%, transparent); color: var(--accent-2); }
code, pre { font-family: var(--mono); font-size: .86rem; }
pre { background: var(--code-bg); padding: 14px 16px; border-radius: 6px; overflow-x: auto; margin: 6px 0 12px; line-height: 1.5; }
button.copy { font: 600 .75rem var(--mono); border: 1px solid var(--line); background: var(--surface); color: var(--fg);
  border-radius: 4px; padding: 3px 8px; cursor: pointer; }
button.copy:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.result { border-left: 3px solid var(--accent); padding: 4px 0 4px 14px; margin: 6px 0 14px; }
a { color: var(--accent); }
footer { font-size: .85rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: 18px; }
@media (max-width: 520px) { main { padding-block: 28px 48px; gap: 40px; } th, td { padding: 6px 8px; } }
"""

JS = """
document.querySelectorAll('button.copy').forEach(b => b.addEventListener('click', async () => {
  const text = b.dataset.copy;
  try { await navigator.clipboard.writeText(text); b.textContent = 'Copied'; }
  catch (e) { const r = document.createRange(); const n = document.getElementById(b.dataset.target);
    if (n) { r.selectNodeContents(n); const s = getSelection(); s.removeAllRanges(); s.addRange(r); } b.textContent = 'Selected'; }
  setTimeout(() => { b.textContent = 'Copy'; }, 1600);
}));
"""


def pherc(scroll_id: str) -> str:
    """'PHerc0306B' -> 'PHerc. 306B'"""
    return re.sub(r"^PHerc0*", "PHerc. ", scroll_id)


def img(path: Path, alt: str) -> str:
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(alt)}" loading="lazy">'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--atlas", default="atlas")
    ap.add_argument("--figures", default="figures")
    ap.add_argument("--out", default="report/index.html")
    ap.add_argument("--site", default="docs/index.html", help="full HTML page for GitHub Pages (serve /docs)")
    ap.add_argument("--repo", default="https://github.com/tkran2/scrollscout")
    a = ap.parse_args()
    R, A, F = Path(a.results), Path(a.atlas), Path(a.figures)
    cv = json.loads((R / "crossval.json").read_text())
    an = json.loads((R / "survey_analysis.json").read_text())
    tr = json.loads((R / "text_regions.json").read_text()) if (R / "text_regions.json").exists() else None
    ts = json.loads((R / "team_segments.json").read_text()) if (R / "team_segments.json").exists() else None
    sm_mesh = json.loads((R / "survey_meshes.json").read_text()).get("summary") if (R / "survey_meshes.json").exists() else None
    census_doc = json.loads((R / "segment_census.json").read_text()) if (R / "segment_census.json").exists() else {}
    census = census_doc.get("segments")
    census_skipped = census_doc.get("skipped", [])
    items = [json.loads(f.read_text()) for f in sorted(A.glob("PHerc*.json"))]
    items.sort(key=lambda d: -d["summary"]["score_p90"])
    dense_dir = A.parent / "atlas_dense"
    dense = {f.stem: json.loads(f.read_text()) for f in sorted(dense_dir.glob("PHerc*.json"))} if dense_dir.exists() else {}
    n_points = sum(d["summary"]["n_points"] for d in items) + sum(
        d["summary"]["n_points"] - next((i["summary"]["n_points"] for i in items if i["summary"]["scroll"] == k), 0)
        for k, d in dense.items())
    pts_per_scroll = items[0]["summary"]["n_points"] if items else 0

    parts = [f"""<title>Scroll Scout</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@500;600&display=swap">
<style>{CSS}</style>
<main>
<header>
  <div class="eyebrow">Vesuvius Challenge · First Letters</div>
  <h1>Scroll Scout</h1>
  <p class="lede">Before anyone spends GPU time on a Herculaneum scroll, Scroll Scout predicts whether a seed point will
  give a clean papyrus surface, and checks whether a segment that has already been traced stays on its sheet, from a
  few megabytes of public CT data, on a laptop CPU. It passes three independent tests and maps all 21 scrolls still
  eligible for the $50,000 First Letters prizes.</p>
  <div class="stats">
    <div class="stat"><b>{(f"{ts['summary']['rule_correct']}/{ts['summary']['rule_n']}" if ts and 'rule_correct' in ts['summary'] else '–')}</b><span>of the team's own segments called right by check-segment, on two scrolls never used to build it (AUC {(ts['summary']['auc'] if ts else float('nan')):.2f})</span></div>
    <div class="stat"><b>{cv['auc']:.2f}</b><span>held-out AUC on 65 judged survey patches</span></div>
    <div class="stat"><b>{len(items) or 21}</b><span>unread scrolls mapped, {n_points:,} points scored</span></div>
    <div class="stat"><b>4.5 s</b><span>per point on one CPU core; no GPU, no downloads beyond the chunks it reads</span></div>
  </div>
</header>

<section>
  <h2>The problem</h2>
  <p>Every attempt to read an unread scroll starts by growing a surface on one papyrus sheet inside the CT scan, then
  running an ink model on it. In crushed parts of a scroll the sheets touch and fuse, the grown surface jumps between
  them, and the ink model sees noise. In the
  <a href="https://github.com/Bullo27/first-letters-survey">First Letters survey</a>, only 12 of 65 automatically
  grown patches on the eligible scrolls stayed on their sheet over most of their area. Ink inference on the rest is
  wasted.</p>
</section>

<section>
  <h2>What the scout sees</h2>
  <p>Around a point, Scroll Scout reads a 3.3 mm cube of the CT and of the published <code>surface-m7</code>
  prediction at pyramid level 1 (17 µm voxels) and measures five things: are the predicted sheets flat, unfused and
  unfragmented, and does the sheet orientation, in the prediction and in the raw CT, avoid swirling?</p>
  <figure class="wide">{img(F / 'fig_examples.png', 'CT and surface prediction at two good and two bad seeds')}
  <figcaption>Two seeds whose patches stayed on the sheet (left) and two whose patches swirled (right). Top: CT.
  Bottom: published surface prediction. Score: higher is cleaner.</figcaption></figure>
</section>

<section>
  <h2>Does it work?</h2>
  <p>Three independent tests, each against labels nobody made for this tool.</p>
  <div class="scroll"><table>
    <tr><th>test</th><th>data</th><th>result</th></tr>
    <tr><td>Survey patches</td><td>65 GrowPatch patches on the 21 eligible scrolls, judged by eye</td>
        <td>held-out AUC {cv['auc']:.2f} ({cv['ci'][0]:.2f}–{cv['ci'][1]:.2f})</td></tr>
    <tr><td>The team's own segments</td><td>20 segments the team grew on PHerc. 800 and 1447, scrolls never used to build the score</td>
        <td>AUC {(ts['summary']['auc'] if ts else float('nan')):.2f}, p = {(ts['summary']['p'] if ts else float('nan')):.4f}</td></tr>
    <tr><td>Known text</td><td>the 18 winning letters in PHerc. 343; the PHerc. 1447 text find</td>
        <td>score above {(tr['PHerc0343']['percentile_of_text_median'] if tr else float('nan')):.0f}% and
        {(tr['PHerc1447']['percentile_of_text_median'] if tr else float('nan')):.0f}% of random points</td></tr>
  </table></div>
  <h3>Survey patches</h3>
  <p>Ground truth is the survey's verdict for each of its 65 patches: did the grown surface stay on the sheet?
  12 did. The score was tested two ways.</p>
  <div class="scroll"><table>
    <tr><th>score</th><th class="num">AUC</th><th>95% CI</th><th class="num">top-10 precision</th></tr>
    <tr><td>no ranking (the survey&#8217;s grid of seeds)</td><td class="num">0.50</td><td>–</td><td class="num">18%</td></tr>
    <tr><td>v1, terms fixed before looking at results</td><td class="num">{an['combined']['auc']:.2f}</td>
        <td>{an['combined']['ci'][0]:.2f}–{an['combined']['ci'][1]:.2f}</td><td class="num">50%</td></tr>
    <tr><td>v2, leave-one-scroll-out</td><td class="num">{cv['auc']:.2f}</td>
        <td>{cv['ci'][0]:.2f}–{cv['ci'][1]:.2f}</td><td class="num">50%</td></tr>
  </table></div>
  <p style="margin-top:12px">Leave-one-scroll-out means: for each of the 21 scrolls, the signals were chosen using the
  other 20 only, then tested on the held-out scroll. The same four signals were chosen in all 21 rounds. Both
  results have a permutation p-value of 0.0002.{(f" Scored over each patch's whole surface with check-segment (12 points per patch rather than the seed alone), the AUC is {sm_mesh['auc']:.2f} ({sm_mesh['ci'][0]:.2f}–{sm_mesh['ci'][1]:.2f}); the score was tuned on these patches, so this is a consistency check rather than a new test." if sm_mesh else "")}</p>
  <figure class="wide">{img(F / 'fig_validation.png', 'ROC curve, scores by survey verdict, and per-signal AUCs')}
  <figcaption>Left: held-out ROC curve. Middle: held-out score of every survey seed against what its patch did.
  Right: each signal in the score on its own.</figcaption></figure>
</section>
"""]

    if ts:
        sm = ts["summary"]
        parts.append(f"""
<section>
  <h2>The team's own segments</h2>
  <p>The team published 21 automatically grown segments for PHerc. 800 and PHerc. 1447, and the survey judged each:
  {sm['n_good']} follow the sheet, {sm['n_bad']} cut obliquely across several layers, 1 is mixed. Neither scroll was used to
  choose or calibrate the score. Scoring 12 points over each segment, every segment that follows the sheet scores
  above every one that cuts across layers: AUC {sm['auc']:.2f}, permutation p = {sm['p']:.4f}. Within PHerc. 1447
  alone (3 good, 11 bad) the separation is also perfect (AUC {sm['auc_within_1447']:.2f}, p = {sm['p_within_1447']:.4f}).</p>
  <figure>{img(F / 'fig_team_segments.png', 'Scores of the team segments by verdict')}</figure>
  <h3>Check a segment before ink detection</h3>
  <p>This test is exactly what <code>scrollscout check-segment</code> does with any traced segment: a tifxyz folder,
  an OBJ mesh or an open-data URL. Its rule was fixed before the test: a segment likely follows the sheet when its
  median point scores above the clean threshold set on the survey (0.63). That rule gets
  {sm.get('rule_correct', '–')} of {sm.get('rule_n', '–')} segments right; the survey's one mixed segment comes out as
  likely to cut across layers. It takes about 15 seconds on 4 CPU cores, against hours of GPU time for ink detection,
  and draws a map of where the segment runs into crushed papyrus.</p>
  <figure class="wide">{img(F / 'fig_segment_check.png', 'check-segment maps of a good and a bad segment')}</figure>
</section>""")

    if census:
        ok = [r for r in census if r["median_score"] is not None and r["median_score"] == r["median_score"]]
        fol = [r for r in ok if r["verdict"].endswith("follows the sheet")]
        scrolls = sorted({r["scroll"] for r in ok}, key=lambda s: -sum(r["scroll"] == s for r in ok))
        skip_html = ""
        if census_skipped:
            sk_scrolls = ", ".join(sorted({pherc(r["scroll"]) for r in census_skipped}))
            sk_um = ", ".join(sorted({f"{r['voxel_um']:g}" for r in census_skipped}))
            skip_html = (f" The {len(census_skipped)} segments of {html.escape(sk_scrolls)} were not checked: they sit "
                         f"on a {sk_um} µm scan, outside the scans the score was validated on.")
        crow = "".join(f"<tr><td>{html.escape(pherc(s))}</td><td class='num'>{sum(r['scroll'] == s for r in ok)}</td>"
                       f"<td class='num'>{sum(r['scroll'] == s for r in fol)}</td></tr>" for s in scrolls)
        parts.append(f"""
<section>
  <h2>Every published segment, checked</h2>
  <p>check-segment ran on every segment in the open-data bucket it can check: the {len(ok)} segments, on
  {len(scrolls)} scrolls, with a tifxyz mesh traced on an 8.6–9.4 µm scan that has a published surface prediction.
  {len(fol)} of {len(ok)} likely follow their sheet. Outside the 20 segments the survey judged, these verdicts are
  predictions: a way to decide which segments to run ink detection on, or train on, first. The full list is
  <code>census/SEGMENTS.md</code> in the repository.{skip_html}</p>
  <div class="scroll"><table>
    <tr><th>scroll</th><th class="num">segments checked</th><th class="num">likely follow the sheet</th></tr>{crow}
  </table></div>
  <figure>{img(F / 'fig_census.png', 'check-segment verdicts per scroll')}</figure>
</section>""")

    if tr:
        rows = "".join(
            f"<tr><td>{html.escape(pherc(s))}</td><td class='num'>{len(r['text_scores'])}</td>"
            f"<td class='num'>{r['text_median']:+.2f}</td><td class='num'>{r['random_median']:+.2f}</td>"
            f"<td class='num'>{r['percentile_of_text_median']:.0f}%</td></tr>" for s, r in tr.items())
        parts.append(f"""
<section>
  <h2>Where text was actually found</h2>
  <p>Two scrolls on the same 8.64 µm, 116 keV scan protocol as most eligible scrolls have produced text: PHerc. 343,
  whose 18 letters won the October First Letters prize, and PHerc. 1447, where the team found text in September.
  The scout scored those exact places against random points inside the same scrolls.</p>
  <div class="scroll"><table>
    <tr><th>scroll</th><th class="num">text points</th><th class="num">text median</th><th class="num">random median</th>
    <th class="num">text beats</th></tr>{rows}
  </table></div>
  <figure>{img(F / 'fig_text_regions.png', 'Scores where text was found versus random points')}</figure>
</section>""")

    if items:
        trs = []
        for i, d in enumerate(items, 1):
            s = d["summary"]
            seed_src = dense.get(s["scroll"], d)
            inn = inner_seeds(seed_src["points"])
            sd = inn[0] if inn else (s["seeds"][0] if s["seeds"] else None)
            pill = "p116" if abs(s["voxel_um"] - 8.64) < 0.05 else "p113"
            proto = f"{s['voxel_um']:.2f} µm · {s['energy_kev']:.0f} keV"
            xyz = (sd.get("xyz") or sd["zyx"][::-1]) if sd else None
            seed = f"{xyz[0]} {xyz[1]} {xyz[2]}" if sd else "–"
            cmd = (f"python fls.py run --scroll {s['scroll']} --seed {seed} --gens 100 --name scout_1" if sd else "")
            button = (f'<button class=copy data-target=seed{i} data-copy="{html.escape(cmd)}">Copy</button>'
                      if cmd else "")
            trs.append(
                f"<tr><td class='num'>{i}</td><td>{pherc(s['scroll'])}</td>"
                f"<td><span class='pill {pill}'>{proto}</span></td><td class='num'>{s['score_median']:+.2f}</td>"
                f"<td class='num'>{s['score_p90']:+.2f}</td><td class='num'>{s['frac_clean']:.0%}</td>"
                f"<td><code id='seed{i}'>{seed}</code></td>"
                f"<td>{button}</td></tr>")
        parts.append(f"""
<section>
  <h2>The atlas</h2>
  <p>{pts_per_scroll} points were spread through each of the 21 eligible scroll volumes (8 heights × 4 distances from
  the axis) and scored; {', '.join(pherc(k) for k in dense) or 'no scroll'} got {max([d['summary']['n_points'] for d in dense.values()] or [0])}
  points each for their seeds. Scrolls are ranked by their best 10% of points from the even pass. The seed shown is each scroll's best point in its
  inner part (within 0.45 of the way from the axis to the outside, away from the top and bottom 15%), where both
  known text finds lie, as level-0 voxel coordinates (x y z) of the eligible volume. Copy puts a ready-to-run
  <a href="https://github.com/Bullo27/first-letters-survey">fls.py</a> command on the clipboard. More seeds per
  scroll, inner and overall, are in <code>atlas/seeds.csv</code>.</p>
  <div class="scroll"><table>
    <tr><th class="num">#</th><th>scroll</th><th>scan</th><th class="num">median</th><th class="num">best 10%</th>
    <th class="num">clean</th><th>inner seed (x y z)</th><th></th></tr>
    {''.join(trs)}
  </table></div>
  <figure class="wide">{img(F / 'fig_atlas_ranking.png', 'Scrolls ranked by scout score')}</figure>
  <figure class="wide">{img(F / 'fig_atlas_maps.png', 'Where the clean papyrus is inside each scroll')}
  <figcaption>Each panel is one scroll, seen as distance from the axis (x) and height (y). Darker dots are cleaner
  papyrus; orange rings are the recommended seeds.</figcaption></figure>
  {''.join(f"<figure class='wide'>{img(F / f'fig_detail_{k}.png', f'Cross-sections of {pherc(k)}')}</figure>" for k in dense)}
</section>""")

    parts.append(f"""
<section>
  <h2>Use it</h2>
<pre>pip install "git+{html.escape(a.repo)}"
scrollscout point PHerc1447 20250521151220 4144 2742 12557     # score one point (x y z)
scrollscout near  PHerc1447 20250521151220 4144 2742 12557     # best seeds around a target
scrollscout scan  PHerc0306B 20250521133212 --points 128        # map one scroll, pick seeds
scrollscout seeds PHerc0306B_20250521133212_scout.json          # seeds and fls.py commands
scrollscout export-vc3d PHerc0306B_20250521133212_scout.json    # colour-coded points for VC3D
scrollscout check-segment path/to/segment.tifxyz --png map.png  # does a traced segment stay on its sheet?
scrollscout atlas --out atlas/                                  # every First Letters volume</pre>
  <p>No GPU, no VC3D install and no full-volume downloads: the tool reads only the chunks it needs from
  <code>s3://vesuvius-challenge-open-data</code>. Source, tests and every script behind these numbers:
  <a href="{html.escape(a.repo)}">{html.escape(a.repo)}</a>.</p>
</section>

<section>
  <h2>Limits</h2>
  <p>All labels were judged by one person (the survey's author), and the team-segment test has 20 segments. Spiral
  fits and lasagna surfaces are untested. check-segment scores the papyrus a segment passes through, not the segment's
  own path, so a segment that jumps layers inside clean papyrus would pass. A clean surface is necessary for reading
  text, not sufficient: the scout says where tracing works, not where the ink is. Its seeds are the best of the sampled points, not the best in the
  scroll.</p>
</section>

<footer>
  CT scans and surface predictions: Vesuvius Challenge open data (CC BY-NC 4.0); figures derived from them carry
  the same licence. Ground truth: First Letters survey by Matteo Bulloni. PHerc. 343 letter locations: Erwin
  Nieuwlaar's winning submission. Code: MIT.
</footer>
</main>
<script>{JS}</script>
""")
    page = "".join(parts)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print("wrote", out, f"{out.stat().st_size / 1e6:.1f} MB")
    if a.site:  # the same page as a complete document, for GitHub Pages
        head, body = page[:page.index("<main>")], page[page.index("<main>"):]
        site = Path(a.site)
        site.parent.mkdir(parents=True, exist_ok=True)
        site.write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                        f'{head}</head>\n<body>\n{body}</body>\n</html>\n')
        print("wrote", site)


if __name__ == "__main__":
    main()
