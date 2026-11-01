import json

import numpy as np
import pytest

from scrollscout import zarrhttp
from scrollscout.zarrhttp import ZArray, to_https


def fake_store(arr, chunks, compressor=None, missing=()):
    """An in-memory zarr v2 array served through a patched zarrhttp._get."""
    meta = {"shape": list(arr.shape), "chunks": list(chunks), "dtype": "|u1", "fill_value": 0, "order": "C",
            "filters": None, "dimension_separator": "/", "compressor": compressor, "zarr_format": 2}
    objects = {"https://example.test/vol/0/.zarray": json.dumps(meta).encode()}
    grid = [range(0, s, c) for s, c in zip(arr.shape, chunks)]
    codec = None
    if compressor:
        from numcodecs import get_codec

        codec = get_codec(compressor)
    for z in grid[0]:
        for y in grid[1]:
            for x in grid[2]:
                idx = (z // chunks[0], y // chunks[1], x // chunks[2])
                if idx in missing:
                    continue
                block = np.zeros(chunks, np.uint8)
                part = arr[z:z + chunks[0], y:y + chunks[1], x:x + chunks[2]]
                block[: part.shape[0], : part.shape[1], : part.shape[2]] = part
                raw = block.tobytes()
                objects[f"https://example.test/vol/0/{idx[0]}/{idx[1]}/{idx[2]}"] = codec.encode(raw) if codec else raw
    return objects


@pytest.fixture
def patched(monkeypatch, tmp_path):
    def install(objects):
        monkeypatch.setattr(zarrhttp, "_get", lambda url, timeout=60.0: objects.get(url))
        monkeypatch.setenv("SCROLLSCOUT_CACHE", str(tmp_path))

    return install


@pytest.mark.parametrize("compressor", [None, {"id": "blosc", "cname": "zstd", "clevel": 1, "shuffle": 1, "blocksize": 0}])
def test_read_region_matches_numpy(patched, compressor):
    rng = np.random.default_rng(0)
    arr = rng.integers(1, 255, (20, 18, 22), dtype=np.uint8)
    patched(fake_store(arr, (8, 8, 8), compressor))
    za = ZArray.open("https://example.test/vol", 0)
    got = za.read(3, 17, 2, 15, 5, 21, workers=2)
    assert np.array_equal(got, arr[3:17, 2:15, 5:21])
    # second read comes from the disk cache
    assert np.array_equal(za.read(0, 20, 0, 18, 0, 22), arr)


def test_missing_chunks_are_fill_value_and_regions_clip(patched):
    arr = np.full((16, 16, 16), 7, np.uint8)
    patched(fake_store(arr, (8, 8, 8), missing={(0, 0, 0)}))
    za = ZArray.open("https://example.test/vol", 0)
    got = za.read(-4, 12, -4, 12, -4, 12)
    assert got.shape == (12, 12, 12)  # clipped to the array
    assert (got[:8, :8, :8] == 0).all() and (got[8:, 8:, 8:] == 7).all()


def test_s3_url_conversion():
    assert to_https("s3://vesuvius-challenge-open-data/PHerc0268/volumes/x.zarr/") == \
        "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0268/volumes/x.zarr"
