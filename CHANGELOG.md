# Changelog

## 0.2.1 (5 November 2026)

- `check-segment --fail-on-cross` exits with status 1 unless every segment likely follows its sheet, so a
  pipeline can stop before running ink detection on a bad segment.
- Fix: OBJ meshes with negative (relative) face indices, which the format allows, now read correctly.
- Fix: with `SCROLLSCOUT_NO_CACHE=1`, `check-segment` no longer writes segment meshes to the cache.
- Offline tests of the command line (`check-segment` with several segments, CSV and `--fail-on-cross`;
  `near`): 35 tests in all.

## 0.2.0 (1 November 2026)

**New: check a segment before ink detection.** `scrollscout check-segment` takes any traced segment (a
tifxyz folder, an OBJ mesh or an open-data URL), scores 12 points spread over it in about 15 seconds on
4 CPU cores, and says whether it likely follows its sheet, with a map of where it runs into crushed
papyrus or leaves the scroll. Its rule was fixed before testing and calls all 20 of the team's segments
that the First Letters survey judged by eye correctly (AUC 1.00). Several segments at once, with a CSV
summary: `scrollscout check-segment paths/* --csv triage.csv`.

**New: every published segment, checked.** `census/SEGMENTS.md` lists check-segment's verdict for all 81
published segments on the 8.6–9.4 µm scans: 45 likely follow their sheet.

**New commands.** `near` finds the cleanest seeds around a target such as a text find; `export-vc3d`
writes scan results as VC3D point collections; `--version`.

**Atlas v0.2.** 128 points per scroll (from 64), 512 for PHerc. 125, 175A, 306B and 483A, cross-section
maps of their best seeds, and VC3D point collections for all 21 First Letters scrolls. The ranking
barely moves against the independent 64-point pass (Spearman 0.93).

**Faster.** A point now takes about 4.5 s on one CPU core (17 s before), with the same held-out AUC
(0.88) on the survey.

**Fixes.** Surface predictions stored on a coarser grid than the CT are read at the right place, or the
point is left unscored instead of being scored wrongly. Scans outside the validated 8.6–9.4 µm range get
a warning. Points past the end of a scan no longer get a score.

**Project.** 30 offline unit tests run on every push (GitHub Actions, Python 3.10 to 3.13); the report
is served from `docs/` with GitHub Pages; `tifffile` and `imagecodecs` are now dependencies.

## 0.1.0

First release: the scout score, validated on the First Letters survey (held-out AUC 0.88) and on where
text has been found, and a 64-point atlas of the 21 First Letters scrolls.
