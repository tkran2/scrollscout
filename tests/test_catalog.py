import json
from importlib import resources
from pathlib import Path

from scrollscout.catalog import Catalog


def test_bundled_catalog_finds_eligible_volumes():
    cat = Catalog.load()
    elig = json.loads(Path(str(resources.files("scrollscout") / "data" / "prize_eligibility_2026-10-31.json")).read_text())
    for e in elig["first-letters-2027"]:
        v = cat.volume(e["scroll"], e["volume"])
        assert v.ct.startswith("s3://vesuvius-challenge-open-data/")
        assert v.surface and "surface" in v.surface
        assert v.voxel_um in (8.64, 9.362)


def test_pherc0268_paths():
    v = Catalog.load().volume("PHerc0268", "20251110183117")
    assert v.ct.rstrip("/").endswith("PHerc0268/volumes/20251110183117-8.640um-1.2m-116keV-masked.zarr")
    assert v.energy_kev == 116
