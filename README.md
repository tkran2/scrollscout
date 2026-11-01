# Scroll Scout

**Find where Herculaneum scroll papyrus is clean enough to trace, from public CT data, on a laptop CPU.**

The [Vesuvius Challenge](https://scrollprize.org) pays $50,000 for the first 10 letters read in a
still-unread scroll (21 eligible scroll volumes, up to 9 more prizes). The first step of every attempt
is the same: grow a surface on the papyrus sheet, then run an ink model on it. Most attempts fail at
that first step. In the [First Letters survey](https://github.com/Bullo27/first-letters-survey), only
12 of 65 automatically grown patches stayed on their sheet over most of their area; the rest crossed
between layers ("layer-crossing swirls") in crushed regions of the scroll, and their ink maps showed
nothing, whatever the model.

Scroll Scout predicts, **before** anyone spends GPU time, whether a seed point will give a clean
surface. It streams a few megabytes of CT and published surface prediction around the point from the
open-data bucket, measures how flat, separate and unfused the papyrus sheets are, and returns one score.
Run over a whole scroll, it maps where the clean papyrus is and recommends seeds.

![What the scout sees](figures/fig_examples.png)

## Does it work?

Validated against the 65 patches of the First Letters survey, each judged by eye as staying on the
sheet or not (12 stayed on it):

| | AUC (95% CI) | top-10 seeds that stayed on the sheet |
|---|---|---|
| no ranking (the survey placed its seeds on a fixed grid) | 0.50 | 18% (base rate) |
| **pre-registered score v1** (terms fixed before looking at results) | **0.84** (0.73–0.93), permutation p = 0.0002 | 50% |
| **score v2, leave-one-scroll-out** (terms chosen on the other 20 scrolls, tested on the held-out one) | **0.88** (0.78–0.95), permutation p = 0.0002 | 50% |

![Validation](figures/fig_validation.png)

Four signals are picked in every one of the 21 cross-validation folds: the predicted sheets are **flat**
(structure-tensor planarity), **not fused** into thick slabs, **not fragmented**, and the raw CT texture
**does not swirl** (the last one is model-independent).

The result does not hinge on where the line between good and bad is drawn, or on the scan type
(all held-out, leave-one-scroll-out):

| comparison | held-out AUC (95% CI) |
|---|---|
| stayed on the sheet over most of the patch or more, vs. the rest | 0.88 (0.78–0.95) |
| on the sheet at least in parts, vs. swirled | 0.87 (0.77–0.95) |
| on the sheet throughout, vs. swirled | 0.97 (0.89–1.00) |
| 8.64 µm / 116 keV scans only (32 patches) | 0.91 |
| 9.36 µm / 113 keV scans only (33 patches) | 0.83 |

### Where text has actually been found

Two scrolls scanned with the same 8.64 µm / 116 keV protocol as half of the eligible scrolls have
produced text. The scout scored those exact places and compared them with random points inside the
same scroll:

| scroll | text location | scout score there | random points (median) | text beats |
|---|---|---|---|---|
| PHerc. 343 | the 18 letters that won the October 2026 First Letters prize, located on the winner's mesh | 0.67 (median of 18; range 0.43–1.04) | 0.20 | 81% of random points |
| PHerc. 1447 | where the team found text on 24 Sept 2026 (x 4144, y 2742, z 12557), and 1.5 mm around it | 1.38 | 0.50 | 100% of random points |

Both finds sit on papyrus the scout rates in the top fifth of its scroll and above its "clean"
threshold, and both lie in the inner third of the scroll (0.2–0.4 of the way from the axis to the
outside). These are two locations, so treat this as agreement with where text has been read, not as
proof that the score finds ink.

![Known text locations](figures/fig_text_regions.png)

## The atlas: all 21 scrolls still eligible for First Letters

1,344 sample points, 64 in each eligible volume (8 heights × 4 distances from the axis), scored at about
5 minutes per scroll on 4 CPU cores.

![Ranking](figures/fig_atlas_ranking.png)

- **Cleanest:** PHerc. 175A (48% of points clean), 125 (39%), 306B (38%) and 1218 (36%).
- **Most crushed:** PHerc. 490B and 268 (2%), 191 and 490A (5%), 175B (8%). Automatic tracing will
  struggle almost everywhere in these.
- **On the 116 keV protocol** of the two scrolls where text has turned up, PHerc. 306B, 175A and 1218 lead.

Top eight, with each scroll's best seed in its inner zone (within 0.45 of the way from the axis to the
outside and away from the top and bottom 15%, where both known text finds lie):

| rank | scroll | scan | share of points clean | best 10% score | best inner seed (x, y, z) |
|---:|---|---|---:|---:|---|
| 1 | PHerc. 306B | 8.64 µm / 116 keV | 38% | 1.20 | 3510, 4681, 8821 |
| 2 | PHerc. 175A | 8.64 µm / 116 keV | 48% | 1.19 | 3260, 5375, 4293 |
| 3 | PHerc. 125 | 9.36 µm / 113 keV | 39% | 1.16 | 4385, 3901, 11725 |
| 4 | PHerc. 846B | 9.36 µm / 113 keV | 34% | 1.13 | 4178, 3539, 6441 |
| 5 | PHerc. 1218 | 8.64 µm / 116 keV | 36% | 1.11 | 4406, 4937, 12661 |
| 6 | PHerc. 826 | 9.36 µm / 113 keV | 33% | 1.05 | 4153, 4416, 13010 |
| 7 | PHerc. 1545 | 9.36 µm / 113 keV | 30% | 1.01 | 3175, 3567, 8794 |
| 8 | PHerc. 211 | 9.36 µm / 113 keV | 34% | 0.99 | 3207, 4207, 8218 |

![Inside each scroll](figures/fig_atlas_maps.png)

All 21 scrolls: [`atlas/SUMMARY.md`](atlas/SUMMARY.md). Every seed (5 overall and 3 inner per scroll):
[`atlas/seeds.csv`](atlas/seeds.csv). Every sample point with all its features: `atlas/<scroll>.json`.

## Quick start

```bash
pip install "git+https://github.com/tkran2/scrollscout"     # or: pip install -e . from a clone

# score one point (level-0 voxel x y z of a volume): here, where the team found text in PHerc. 1447
scrollscout point PHerc1447 20250521151220 4144 2742 12557
#  -> "score": 1.38, "verdict": "clean (good seed)"   (15 s on a laptop CPU)

# scan a whole scroll volume: 64 sample points, ~10 min on 4 CPU cores, then seeds
scrollscout scan PHerc0268 20251110183117 --points 64 --out PHerc0268.json
scrollscout seeds PHerc0268.json

# every First Letters eligible volume, ranked
scrollscout atlas --out atlas/
```

No GPU, no VC3D install, no full-volume downloads: everything streams chunk by chunk from
`s3://vesuvius-challenge-open-data` over HTTPS (public, no account). Chunks are cached in
`~/.cache/scrollscout` (set `SCROLLSCOUT_CACHE` to move it, or `SCROLLSCOUT_NO_CACHE=1` to stream only).
Use `--live` to read the current open-data catalog instead of the bundled 31 Oct 2026 snapshot.

The seeds plug straight into VC3D (*Create Segment (GrowPatch)*) or the survey's tool:
`python fls.py run --scroll PHerc0268 --seed X Y Z --gens 100`.

## How it works

For each point, Scroll Scout reads a 192³-voxel cube (3.3 mm at 8.6 µm) at pyramid level 1 of both the
CT and the published `surface-m7` prediction, and measures:

| signal | what it measures | why |
|---|---|---|
| `pred_planarity` | energy-weighted (λ₁−λ₂)/λ₁ of the structure tensor of the prediction | flat, parallel sheets have one dominant gradient direction |
| `pred_thick` | share of predicted surface deeper than 2 voxels from its boundary | in crushed regions the model predicts fused slabs instead of thin sheets ([Jeong](https://github.com/Jinhojeong/vesuvius-surface-geometry-diagnostic)) |
| `pred_ncomp_per_kvox` | connected fragments per 1,000 predicted voxels | continuous sheets vs. broken bits |
| `pred_dispersion` | spread of the dominant sheet normal across 48³ sub-blocks | swirls and folds turn the sheets inside the cube |
| `ct_dispersion` | the same on the raw CT | a model-independent check |

Each signal is z-scored against the survey reference set and signed so that higher = cleaner; the
score is their mean (`scrollscout/score.py`). A seed is "clean" above 0.63, the score that 75% of the
survey's on-sheet seeds exceed.

## Reproduce everything

```bash
python -I scripts/eval_survey.py --survey data/first_letters_survey_results.json \
    --index data/catalog_index_2026-10-31.json --out results/survey_features.json   # ~10 min
python -I scripts/analyze_survey.py results/survey_features.json                  # v1 score, per-signal AUCs
python -I scripts/crossval.py results/survey_features.json                        # v2, leave-one-scroll-out
python -I scripts/eval_text_regions.py --index data/catalog_index_2026-10-31.json \
    --calibration results/calibration.json --n-random 40 --out results/text_regions.json \
    --mesh <pherc343-first-letters>/outputs/concat_w047-w048_R5B2_z9500-11000.tifxyz \
    --letters <pherc343-first-letters>/inputs/concat_w047-w048_R5B2_z9500-11000_letter_boxes.json
SCROLLSCOUT_NO_CACHE=1 python -I scripts/build_atlas.py --index data/catalog_index_2026-10-31.json \
    --eligibility data/prize_eligibility_2026-10-31.json --calibration results/calibration.json \
    --points 64 --out atlas                                                       # ~1.7 h on 4 cores
python -I scripts/summarize_atlas.py atlas
python -I scripts/make_figures.py
python -m pytest tests                                                            # 20 tests
```

## Limitations

- **The labels come from one survey**: 65 patches grown with GrowPatch's default parameters, judged by
  one person. A score that predicts GrowPatch success may not transfer unchanged to other tracers
  (spiral fits, lasagna). The leave-one-scroll-out test shows it transfers across scrolls; more labels
  would tighten the intervals.
- **A clean surface is necessary, not sufficient.** The scout says where tracing will work, not where
  the ink is. It is meant to point ink models at the places where they have a chance.
- **Sampling is coarse.** 64 points per scroll cover each scroll in 8 height × 4 radius bands; the atlas
  seeds are the best of those, not the best in the scroll. `scrollscout scan --points 256` samples
  more densely.
- The score inherits the blind spots of the `surface-m7` model it partly reads.

## Credits and data

- CT scans and surface predictions: [Vesuvius Challenge](https://scrollprize.org) open data, CC BY-NC 4.0.
  Figures derived from them carry the same licence.
- Ground truth: the [First Letters survey](https://github.com/Bullo27/first-letters-survey) by Matteo Bulloni (MIT).
- PHerc. 343 letter locations: [Erwin Nieuwlaar's winning submission](https://github.com/Nieuwlaar/pherc343-first-letters) (MIT).
- Catalog and prize eligibility: [ScrollPrize/villa](https://github.com/ScrollPrize/villa), snapshot of 31 October 2026.

Code: MIT.
