import json

import numpy as np

from scrollscout.atlas import pick_seeds, seed_commands
from scrollscout.cli import main
from scrollscout.sampling import CoarseScroll, sample_points


def test_pick_seeds_best_first_and_spread_out():
    rows = [{"zyx": [0, 0, 0], "score": 1.0}, {"zyx": [10, 0, 0], "score": 0.9},  # too close to the first
            {"zyx": [5000, 0, 0], "score": 0.5}, {"zyx": [0, 9000, 0], "score": float("nan")}]
    seeds = pick_seeds(rows, k=5, min_sep_vox=1500)
    assert [s["score"] for s in seeds] == [1.0, 0.5]


def test_seed_commands_use_xyz_order():
    s = {"scroll": "PHerc0268", "seeds": [{"xyz": [1, 2, 3]}]}
    assert seed_commands(s) == ["python fls.py run --scroll PHerc0268 --seed 1 2 3 --gens 100 --name scout_1"]


def synthetic_scroll():
    z, y, x = np.indices((40, 50, 50))
    r = np.hypot(y - 25, x - 25)
    mask = (r < 20) & (z > 2) & (z < 37)
    vol = np.where(mask, 120, 0).astype(np.uint8)
    center = np.full((40, 2), np.nan)
    radius = np.zeros(40)
    center[3:37] = (25, 25)
    radius[3:37] = 20
    return CoarseScroll(5, 32, vol, mask, mask, center, radius, (3, 36))


def test_sample_points_inside_papyrus_and_stratified():
    cs = synthetic_scroll()
    pts = sample_points(cs, 64, seed=0)
    assert 30 <= len(pts) <= 64
    rf = np.array([cs.radius_fraction(p) for p in pts])
    zf = np.array([cs.z_fraction(p) for p in pts])
    assert (rf < 1.0).all() and (zf > 0).all() and (zf < 1).all()
    assert rf.min() < 0.3 and rf.max() > 0.6  # spans centre to outer layers
    assert zf.min() < 0.25 and zf.max() > 0.75  # spans the height


def test_cli_seeds_prints_commands(tmp_path, capsys):
    f = tmp_path / "scan.json"
    f.write_text(json.dumps({"summary": {"scroll": "PHerc0268", "volume": "v", "voxel_um": 8.64,
                                         "seeds": [{"xyz": [7, 8, 9], "score": 1.2, "r_frac": 0.4, "z_frac": 0.5}]}}))
    main(["seeds", str(f)])
    out = capsys.readouterr().out
    assert "x=7 y=8 z=9" in out and "--seed 7 8 9" in out
