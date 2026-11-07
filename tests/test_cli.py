"""The command line end to end, offline: the CT reads are replaced by features with a chosen score."""

import csv
import json

import numpy as np
import pytest

from scrollscout import atlas, segment
from scrollscout.cli import _calibration, main
from scrollscout.sampling import CoarseScroll
from scrollscout.score import SCORE_TERMS_SIGNED

tifffile = pytest.importorskip("tifffile")
VOL = ["--scroll", "PHerc0800", "--volume", "20250521135224"]


def feats_for(score: float) -> dict:
    """Features whose every score term sits `score` standard deviations on the clean side."""
    cal = _calibration()
    f = {"ct_valid": 1.0}
    for name, sign in SCORE_TERMS_SIGNED:
        f[name] = cal.stats[name]["mean"] + sign * score * cal.stats[name]["sd"]
    return f


def tifxyz(folder, x0):
    folder.mkdir(parents=True)
    r, c = np.indices((20, 30)).astype(np.float32)
    for name, a in zip("xyz", (x0 + 20 * c, 5000 + 0 * c, 8000 + 20 * r)):
        tifffile.imwrite(folder / f"{name}.tif", a)
    return folder


def fake_features(vol, pts, workers=4, log=None):
    """Clean papyrus left of x = 6000, crushed papyrus right of it."""
    for i, p in enumerate(pts, 1):
        if log:
            log(f"  [{i}/{len(pts)}] zyx={p}")
    return [{"zyx": [int(v) for v in p], "features": feats_for(1.2 if p[2] < 6000 else -1.0)} for p in pts]


def test_check_segment_triages_several_and_fails_on_cross(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(segment, "features_at_many", fake_features)
    good, bad = tifxyz(tmp_path / "good.tifxyz", 3000), tifxyz(tmp_path / "bad.tifxyz", 9000)
    table = tmp_path / "triage.csv"
    args = ["check-segment", str(good), str(bad), *VOL, "--workers", "1", "--csv", str(table), "--json", str(tmp_path / "j")]
    main(args)
    out = capsys.readouterr().out
    assert "good.tifxyz: LIKELY FOLLOWS THE SHEET" in out and "bad.tifxyz: LIKELY CUTS ACROSS LAYERS" in out
    assert "1 of 2 likely follow their sheet" in out
    rows = list(csv.DictReader(open(table)))
    assert [r["verdict"] for r in rows] == ["likely follows the sheet", "likely cuts across layers"]
    assert json.loads((tmp_path / "j" / "good.tifxyz.json").read_text())["summary"]["n_points"] == 12
    with pytest.raises(SystemExit, match="1 of 2"):
        main(args + ["--fail-on-cross"])
    main(["check-segment", str(good), *VOL, "--workers", "1", "--fail-on-cross"])  # passes: no exit


def test_check_segment_fails_on_a_segment_it_cannot_read(tmp_path, monkeypatch):
    monkeypatch.setattr(segment, "features_at_many", fake_features)
    good = tifxyz(tmp_path / "good.tifxyz", 3000)
    with pytest.raises(SystemExit, match="1 of 2"):
        main(["check-segment", str(good), str(tmp_path / "missing"), *VOL, "--workers", "1", "--fail-on-cross"])


def synthetic_scroll():
    z, y, x = np.indices((40, 50, 50))
    mask = (np.hypot(y - 25, x - 25) < 20) & (z > 2) & (z < 37)
    center = np.full((40, 2), np.nan)
    radius = np.zeros(40)
    center[3:37] = (25, 25)
    radius[3:37] = 20
    return CoarseScroll(5, 32, np.where(mask, 120, 0).astype(np.uint8), mask, mask, center, radius, (3, 36))


def test_near_ranks_the_grid_around_a_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(atlas, "load_coarse", lambda url: synthetic_scroll())

    def fake(vol, pts, workers, level, half, log=None):  # cleanest along x = 800
        return [{"zyx": [int(v) for v in p], "features": feats_for(1.0 - 0.001 * abs(p[2] - 800))} for p in pts]

    monkeypatch.setattr(atlas, "features_at_many", fake)
    out = tmp_path / "near.json"
    main(["near", "PHerc0800", "20250521135224", "800", "800", "640", "--step", "64", "--workers", "1",
          "--out", str(out)])
    text = capsys.readouterr().out
    assert "target x=800 y=800 z=640: score +1.00, clean" in text
    assert "python fls.py run --scroll PHerc0800 --seed 800" in text
    res = json.loads(out.read_text())
    assert len(res["points"]) == 27
    assert all(s["xyz"][0] == 800 for s in res["summary"]["seeds"])


@pytest.mark.parametrize("bad", [["--points", "0"], ["--workers", "-2"], ["--points", "many"]])
def test_numeric_options_must_be_positive_whole_numbers(bad, capsys):
    with pytest.raises(SystemExit) as e:
        main(["check-segment", "somewhere.tifxyz", *bad])
    err = capsys.readouterr().err
    assert e.value.code == 2 and ("at least 1" in err or "whole number" in err)


def test_quiet_hides_per_point_progress(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(segment, "features_at_many", fake_features)
    good = tifxyz(tmp_path / "good.tifxyz", 3000)
    main(["check-segment", str(good), *VOL, "--workers", "1"])
    assert "[1/12]" in capsys.readouterr().err
    main(["--quiet", "check-segment", str(good), *VOL, "--workers", "1"])
    captured = capsys.readouterr()
    assert "[1/12]" not in captured.err and "LIKELY FOLLOWS THE SHEET" in captured.out
