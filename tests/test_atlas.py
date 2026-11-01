import json

import numpy as np

from scrollscout.atlas import grid_near, merge_scans, pick_seeds, seed_commands, summarize
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


def test_vc3d_export_format(tmp_path):
    from scrollscout.vc3d import to_point_collections

    scan = {"summary": {"scroll": "PHerc0268", "seeds": [{"zyx": [30, 20, 10], "score": 1.2}]},
            "points": [{"zyx": [30, 20, 10], "score": 1.2, "r_frac": 0.2, "z_frac": 0.5},
                       {"zyx": [3, 2, 1], "score": -0.5, "r_frac": 0.8, "z_frac": 0.5},
                       {"zyx": [9, 8, 7], "score": 0.3, "r_frac": 0.3, "z_frac": 0.4}]}
    doc = to_point_collections(scan, 0.63)
    assert doc["vc_pointcollections_json_version"] == "1"
    cols = list(doc["collections"].values())
    assert all({"uuid", "name", "points", "metadata", "color"} <= set(c) for c in cols)
    clean, middling, crushed = cols[0], cols[1], cols[2]
    assert [p["p"] for p in clean["points"].values()] == [[10.0, 20.0, 30.0]]  # x, y, z order
    assert len(middling["points"]) == 1 and len(crushed["points"]) == 1


def test_in_papyrus_and_grid_near():
    cs = synthetic_scroll()  # factor 32: papyrus within radius 20 coarse voxels of (25, 25), z 3..36
    centre = cs.to_level0((20, 25, 25))
    assert cs.in_papyrus(centre) and not cs.in_papyrus(cs.to_level0((20, 25, 47)))
    assert not cs.in_papyrus([-5, 0, 0]) and not cs.in_papyrus(cs.to_level0((99, 25, 25)))
    pts = grid_near(cs, centre, step=64, size=3)
    assert len(pts) == 27 and pts[0] == [int(round(v)) for v in centre]
    edge = cs.to_level0((20, 25, 44))  # near the outside: part of the grid falls off the papyrus
    pts = grid_near(cs, edge, step=200, size=3)
    assert pts[0] == [int(round(v)) for v in edge] and len(pts) < 27
    assert all(cs.in_papyrus(p) for p in pts[1:])


class _Cal:
    stats = {"_good_threshold": {"value": 0.5}}


def test_summarize_ignores_unscorable_points_and_merge_keeps_both():
    rows = [{"zyx": [0, 0, 0], "score": 1.0, "r_frac": 0.2, "z_frac": 0.5},
            {"zyx": [0, 0, 3000], "score": 0.0, "r_frac": 0.3, "z_frac": 0.5},
            {"zyx": [0, 3000, 0], "score": float("nan"), "r_frac": 0.3, "z_frac": 0.5}]
    s = summarize(rows, _Cal())
    assert s["n_points"] == 2 and s["frac_clean"] == 0.5 and s["score_median"] == 0.5
    assert [x["xyz"] for x in s["seeds"]] == [[0, 0, 0], [3000, 0, 0]]
    a = {"summary": {"scroll": "X", "secs": 5}, "points": rows[:1], "coarse": {}}
    b = {"summary": {"scroll": "X", "secs": 7}, "points": rows[1:], "coarse": {}}
    m = merge_scans(a, b, _Cal())
    assert m["summary"]["n_points"] == 2 and m["summary"]["secs"] == 12 and len(m["points"]) == 3
