# Progress prize submission (draft)

Form: the "Progress Prizes" submission form on https://scrollprize.org/prizes (monthly; next deadline
11:59pm Pacific, November 30, 2026). Release first, post on the Discord, then submit: the team favours
work that is released early and gets used.

---

**Title:** Scroll Scout: check a segment before ink detection and find seeds that stay on the sheet,
for any scroll, from public data on a CPU. All 20 of the team's own judged segments called right (AUC
1.00), held-out AUC 0.88 on the First Letters survey, and seeds plus VC3D point collections for all 21
First Letters scrolls

**Repository:** https://github.com/tkran2/scrollscout (MIT)

**What it does.** Scroll Scout scores any point of a scroll volume by how cleanly the papyrus sheets
around it are separated: whether the published `surface-m7` prediction there shows thin, flat,
unfused, unfragmented sheets, and whether the raw CT texture swirls. It streams ~20 MB of CT and
prediction chunks per point straight from `s3://vesuvius-challenge-open-data` (OME-Zarr, no account,
no GPU, no VC3D install), about 4.5 s per point on one CPU core. Three uses:
- **Check a traced segment** (`check-segment`): give it a tifxyz folder, an OBJ mesh or an open-data URL;
  in about 15 s on 4 cores it says whether the segment likely follows its sheet and maps where it runs
  into crushed papyrus or leaves the scroll, before hours of GPU ink detection are spent on it.
- **Find seeds** (`scan`, `near`): run over a scroll, or around a target such as a text find, it
  recommends seeds as level-0 voxel coordinates for VC3D's *Create Segment (GrowPatch)* or
  `fls.py run --seed X Y Z`.
- **Map every eligible scroll** (`atlas`), with colour-coded VC3D point collections (`export-vc3d`).

**Why it matters.** The "compressed or highly curved regions" bottleneck in the 2026 Open Problems:
in the First Letters survey only 12 of 65 automatically grown patches stayed on their sheet over most
of their area, and every GPU-hour of ink inference on the rest is wasted. Scroll Scout flags those
failure cases twice: before tracing (where to seed) and after it (which segments, and which parts of
them, are worth ink inference).

**Evidence on real data (three independent tests).**
1. *The team's own segments.* 20 automatically grown segments the team published for PHerc. 800 and
   1447, two scrolls never used to build or calibrate the score, judged by eye in the survey (9 follow
   the sheet, 11 cut across layers), run through `check-segment`: every good segment scores above every
   bad one, AUC 1.00, permutation p = 0.0002 (within PHerc. 1447 alone, 3 vs 11, also AUC 1.00,
   p = 0.0014), and its verdict, with a rule fixed before the test (median point above the survey's
   clean threshold), is right for 20 of 20.
2. *Survey patches.* 65 GrowPatch patches on the 21 eligible scrolls: pre-registered score AUC 0.84
   (0.72–0.93); leave-one-scroll-out AUC 0.88 (0.78–0.95), the same four signals chosen in all 21
   folds; 50% of the top 10 seeds stayed on the sheet against an 18% base rate. Robust to the label
   cut-off (0.87 / 0.97) and the scan type (0.91 at 8.64 µm, 0.83 at 9.36 µm).
3. *Known text.* The 18 letters of the PHerc. 343 First Letters win score above 78% of random points
   in that scroll; the PHerc. 1447 text location announced on 24 September scores above all of them.
   Both lie in the inner third of their scroll.

**Atlas.** <!-- ATLAS_LINE -->4,224 points scored over all 21 First Letters volumes. Cleanest: PHerc. 175A, PHerc. 125, PHerc. 306B; most crushed: PHerc. 268, PHerc. 490B, PHerc. 175B, where automatic tracing will struggle almost everywhere. PHerc. 125, 175A, 306B and 483A, the most promising, were scanned at 512 points each. The ranking barely moves between two passes over different points (Spearman 0.93). Every scroll gets seeds (5 overall, 3 in the inner zone where both known text finds lie) with ready-to-run fls.py commands, and a VC3D point-collections file.<!-- /ATLAS_LINE -->

**Census.** <!-- CENSUS_LINE -->`check-segment` on every published segment it can check (81 segments on 5 scrolls, all on 8.6–9.4 µm scans): 45 likely follow their sheet. The list (census/SEGMENTS.md, census/segments.csv) says which segments are worth ink detection or training first.<!-- /CENSUS_LINE -->

**Use.** `pip install` the repo, then `scrollscout check-segment | near | point | scan | seeds |
export-vc3d | atlas`. 43 offline unit tests run on every push (GitHub Actions, Python 3.10 to 3.13);
every number above is reproduced by the scripts listed in the README.

---

## Discord post (draft, #general or the First Letters channel)

> Released **Scroll Scout**: from public data and on a laptop CPU, it checks whether a traced segment
> stays on its sheet before you spend GPU time on ink detection (`scrollscout check-segment
> <tifxyz|obj|s3 url>`, ~15 s), and finds seeds likely to stay on the sheet. On the team's own 20
> auto-grown segments for PHerc. 800/1447 it calls all 20 right (AUC 1.00, rule fixed beforehand), and
> on the 65 patches of Matteo's First Letters survey it gets held-out AUC 0.88. Also: an atlas of all 21
> First Letters scrolls with seeds, cross-section maps of the best ones, and VC3D point collections.
> Happy to hear where it's wrong! https://github.com/tkran2/scrollscout
