# Progress prize submission (draft)

Form: the "Progress Prizes" submission form on https://scrollprize.org/prizes (monthly; next deadline
11:59pm Pacific, November 30, 2026). Release first, post on the Discord, then submit: the team favours
work that is released early and gets used.

---

**Title:** Scroll Scout: predict where a GrowPatch seed will stay on the sheet, for any scroll, from
public data on a CPU (held-out AUC 0.88), with seeds for all 21 First Letters scrolls

**Repository:** https://github.com/tkran2/scrollscout (MIT)

**What it does.** Scroll Scout scores any point of a scroll volume by how cleanly the papyrus sheets
around it are separated: whether the published `surface-m7` prediction there shows thin, flat,
unfused, unfragmented sheets, and whether the raw CT texture swirls. It streams ~20 MB of CT and
prediction chunks per point straight from `s3://vesuvius-challenge-open-data` (OME-Zarr, no account,
no GPU, no VC3D install). Run over a scroll, it maps where the traceable papyrus is and recommends
seeds, written as level-0 voxel coordinates that go straight into VC3D's *Create Segment (GrowPatch)*
or `fls.py run --seed X Y Z`.

**Why it matters.** The "compressed or highly curved regions" bottleneck in the 2026 Open Problems:
most automatically grown patches on the First Letters scrolls leave their sheet (53 of 65 in the
First Letters survey), and every GPU-hour of ink inference on those patches is wasted. Scroll Scout
flags those failure cases before any tracing or inference is run.

**Evidence on real data.** Ground truth: the 65 patches of the First Letters survey (Bulloni), each
judged by eye.
- Pre-registered score (terms fixed before looking at results): AUC 0.84 (95% CI 0.73–0.93),
  permutation p = 0.0002.
- Leave-one-scroll-out (terms chosen on 20 scrolls, tested on the 21st, for every scroll): AUC 0.88
  (0.78–0.95), p = 0.0002. The same four signals are chosen in all 21 folds.
- Of the 10 best-scoring seeds, 50% stayed on the sheet, against an 18% base rate.
- Known text locations on the 116 keV protocol: the 18 letters of the PHerc. 343 First Letters win
  score above 81% of random points in that scroll; the PHerc. 1447 text location announced on
  24 September scores above all of them. Both lie in the inner third of their scroll.
- Robust to the label cut-off (on-sheet-in-parts vs. swirled: held-out AUC 0.87; throughout vs.
  swirled: 0.97) and to the scan type (0.91 on 8.64 µm, 0.83 on 9.36 µm).

**Atlas.** 64 sample points in each of the 21 eligible volumes, a ranking of the scrolls by how much
clean papyrus they have, and five seeds per scroll (`atlas/SUMMARY.md`, `atlas/seeds.csv`).
Cleanest: PHerc. 175A, PHerc. 125, PHerc. 306B, PHerc. 1218; most crushed: PHerc. 490B, PHerc. 268, PHerc. 191.

**Use.** `pip install` the repo, then `scrollscout point <scroll> <volume> X Y Z`,
`scrollscout scan <scroll> <volume>`, `scrollscout atlas`. 20 unit tests; every number above is
reproduced by the scripts listed in the README.

---

## Discord post (draft, #general or the First Letters channel)

> Released **Scroll Scout**: it predicts, from public data and on a laptop CPU, whether a GrowPatch seed
> will stay on its sheet. Tested on the 65 patches of Matteo's First Letters survey: held-out AUC 0.88
> (leave-one-scroll-out). Includes an atlas of all 21 First Letters scrolls with 5 seeds each, ready
> for VC3D or fls.py. Happy to hear where it's wrong! https://github.com/tkran2/scrollscout
