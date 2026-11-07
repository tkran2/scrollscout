import json

import numpy as np
import pytest

from scrollscout.catalog import Catalog
from scrollscout.segment import (CROSSES, FOLLOWS, Surface, infer_volume, load_surface, no_papyrus, node_scores,
                                 plot_check, read_obj, spread_nodes, to_point_collections)

tifffile = pytest.importorskip("tifffile")


def write_tifxyz(folder, meta=None, hole=True):
    """A 40 x 60 grid on a gently curved sheet, 20 voxels per step, with an invalid corner."""
    folder.mkdir(parents=True)
    r, c = np.indices((40, 60)).astype(np.float32)
    X = 3000 + 20 * c
    Y = 5000 + 0.002 * (20 * c - 600) ** 2
    Z = 8000 + 20 * r
    if hole:
        for a in (X, Y, Z):
            a[:5, :5] = -1
    for name, a in zip("xyz", (X, Y, Z)):
        tifffile.imwrite(folder / f"{name}.tif", a.astype(np.float32))
    (folder / "meta.json").write_text(json.dumps(meta or {"format": "tifxyz", "scale": [0.05, 0.05]}))
    return folder


def test_read_tifxyz_drops_invalid_nodes_and_keeps_grid_coordinates(tmp_path):
    s = load_surface(str(write_tifxyz(tmp_path / "seg.tifxyz")))
    assert s.grid_shape == (40, 60)
    assert len(s.zyx) == 40 * 60 - 25
    assert s.zyx[:, 0].min() >= 8000 and s.zyx[:, 2].min() >= 3000  # z, y, x order
    assert (s.uv >= 0).all()


def test_spread_nodes_are_distinct_and_cover_the_surface(tmp_path):
    s = load_surface(str(write_tifxyz(tmp_path / "seg.tifxyz")))
    idx = spread_nodes(s, 12)
    assert len(set(idx.tolist())) == 12
    uv = s.uv[idx]
    assert np.ptp(uv[:, 0]) > 30 and np.ptp(uv[:, 1]) > 45  # reaches across most of the grid
    assert spread_nodes(s, 100000).size == len(s.zyx)


def test_read_obj_with_and_without_texture(tmp_path):
    p = tmp_path / "mesh.obj"
    p.write_text("v 10 20 30\nv 11 20 30\nv 10 21 31\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n")
    s = read_obj(p)
    assert s.zyx.tolist() == [[30, 20, 10], [30, 20, 11], [31, 21, 10]]
    assert s.uv.tolist() == [[0, 0], [0, 1], [1, 0]]  # (v, u) so that rows go down the page
    q = tmp_path / "plain.obj"
    q.write_text("v 0 0 0\nv 100 0 0\nv 0 100 0\nv 100 100 1\nf 1 2 3\n")
    assert read_obj(q).uv.shape == (4, 2)


def test_infer_volume_from_meta_and_path(tmp_path):
    cat = Catalog.load()
    seg = write_tifxyz(tmp_path / "PHerc0800" / "seg.tifxyz",
                       meta={"target_volume": "20250521135224-surface-20260413222639-surface-m7-L0-th0.2.zarr"})
    v = infer_volume(load_surface(str(seg)), cat)
    assert (v.scroll, v.volume) == ("PHerc0800", "20250521135224")
    seg2 = write_tifxyz(tmp_path / "x" / "20251028213516-on-20250521135224-8.64um.tifxyz")
    v2 = infer_volume(load_surface(str(seg2)), cat, scroll="PHerc0800")
    assert v2.volume == "20250521135224"
    with pytest.raises(ValueError, match="--scroll"):
        infer_volume(load_surface(str(seg2)), cat)
    seg3 = write_tifxyz(tmp_path / "PHerc0500P2" / "segments" / "s" / "mesh" / "20250609-on-20250526151718-2.2um.tifxyz")
    assert infer_volume(load_surface(str(seg3)), cat).scroll == "PHerc0500P2"  # names with letters and digits after


def fake_result(surface, scores, thr=0.63):
    idx = spread_nodes(surface, len(scores))
    pts = [{"zyx": [int(v) for v in surface.zyx[i]], "uv": surface.uv[i].tolist(), "score": s}
           for i, s in zip(idx, scores)]
    med = float(np.median(scores))
    return {"summary": {"segment": surface.name, "threshold": thr, "median_score": med,
                        "frac_clean": float(np.mean(np.array(scores) > thr)),
                        "verdict": FOLLOWS if med > thr else CROSSES}, "points": pts}


def test_node_scores_take_the_nearest_sample(tmp_path):
    s = Surface("t", np.zeros((4, 3)), np.array([[0, 0], [0, 1], [0, 9], [0, 10]], float))
    res = {"points": [{"uv": [0, 0], "score": 1.0}, {"uv": [0, 10], "score": -2.0}, {"uv": [0, 5], "score": np.nan}]}
    assert node_scores(s, res).tolist() == [1.0, 1.0, -2.0, -2.0]


def test_map_and_vc3d_export(tmp_path):
    pytest.importorskip("matplotlib")
    s = load_surface(str(write_tifxyz(tmp_path / "seg.tifxyz")))
    res = fake_result(s, [1.2, 1.1, -0.8, 0.3, 1.0, 0.9])
    res["points"][2]["features"] = {"ct_valid": 0.0}
    res["summary"]["no_papyrus"] = [res["points"][2]["zyx"][::-1]]
    plot_check(s, res, tmp_path / "map.png")
    assert (tmp_path / "map.png").stat().st_size > 5000
    doc = to_point_collections(res)
    assert doc["vc_pointcollections_json_version"] == "1"
    sizes = [len(c["points"]) for c in doc["collections"].values()]
    assert sizes == [4, 1, 1]  # clean, middling, crushed
    p = next(iter(doc["collections"]["0"]["points"].values()))["p"]
    z, y, x = res["points"][0]["zyx"]
    assert p == [x, y, z]


def test_no_papyrus_flag():
    assert no_papyrus({"features": {"ct_valid": 0.0}})
    assert not no_papyrus({"features": {"ct_valid": 0.6}})
    assert not no_papyrus({"features": {"error": "timeout"}})
    assert not no_papyrus({"score": 1.0})


def test_read_obj_negative_indices_count_back_from_the_last_vertex(tmp_path):
    p = tmp_path / "rel.obj"
    p.write_text("v 10 20 30\nv 11 20 30\nv 10 21 31\nvt 0 0\nvt 1 0\nvt 0 1\nf -3/-3 -2/-2 -1/-1\n")
    q = tmp_path / "abs.obj"
    q.write_text("v 10 20 30\nv 11 20 30\nv 10 21 31\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n")
    assert read_obj(p).uv.tolist() == read_obj(q).uv.tolist() == [[0, 0], [0, 1], [1, 0]]


def fake_bucket(monkeypatch):
    """Serve one tifxyz segment from memory in place of the open-data bucket."""
    import io

    from scrollscout import segment

    key = "PHerc0800/segments/seg1/mesh/seg1-on-20250521135224-8.64um.tifxyz/"
    r, c = np.indices((20, 30)).astype(np.float32)
    files = {}
    for name, a in zip("xyz", (3000 + 20 * c, 5000 + 0 * c, 8000 + 20 * r)):
        buf = io.BytesIO()
        tifffile.imwrite(buf, a)
        files[f"{segment.BUCKET_HTTPS}/{key}{name}.tif"] = buf.getvalue()
    files[f"{segment.BUCKET_HTTPS}/{key}meta.json"] = b'{"format": "tifxyz"}'
    monkeypatch.setattr(segment, "_get", lambda url, timeout=60.0: files.get(url))
    monkeypatch.setattr(segment, "list_prefixes",
                        lambda prefix: [key] if prefix == "PHerc0800/segments/seg1/mesh/" else [])


def test_no_cache_leaves_nothing_on_disk(tmp_path, monkeypatch):
    fake_bucket(monkeypatch)
    monkeypatch.setenv("SCROLLSCOUT_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("SCROLLSCOUT_NO_CACHE", "1")
    s = load_surface("s3://vesuvius-challenge-open-data/PHerc0800/segments/seg1/")
    assert len(s.zyx) == 20 * 30 and s.name == "seg1"
    assert not (tmp_path / "cache").exists()
    assert infer_volume(s, Catalog.load()).volume == "20250521135224"  # still read from the bucket key
    monkeypatch.delenv("SCROLLSCOUT_NO_CACHE")
    load_surface("s3://vesuvius-challenge-open-data/PHerc0800/segments/seg1/")
    assert len(list((tmp_path / "cache").rglob("*.tif"))) == 3
