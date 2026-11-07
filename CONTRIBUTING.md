# Contributing

Bug reports, wrong verdicts and pull requests are all welcome.

## Set up

```bash
git clone https://github.com/tkran2/scrollscout
cd scrollscout
python -m venv .venv && . .venv/bin/activate
pip install -e ".[figures,test]"
```

## Before you open a pull request

```bash
python -m pytest -q tests              # offline: no network, no GPU, about 2 seconds
python -m pyflakes scrollscout scripts tests
```

Every test runs offline. Code that reads the open-data bucket is tested by swapping the reads for
in-memory data (see `tests/test_cli.py` and `tests/test_segment.py`), so please do the same for new
features. The package supports Python 3.10 and later.

## Report a wrong verdict

The most useful report is a segment that `check-segment` gets wrong. Please include:

1. the segment (an open-data URL, or the tifxyz folder or OBJ file if it is not public),
2. what you saw when you looked at it (follows the sheet, or crosses layers, and where), and
3. the output of `scrollscout check-segment <segment> --json check.json --png map.png`, with both files attached.

## Changing the score

The score's terms and its 0.63 threshold were fixed on the First Letters survey and then tested on data
they never saw. A change to either needs the evaluation scripts re-run (see "Reproduce everything" in the
README) and the old and new numbers side by side in the pull request.
