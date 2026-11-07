"""Scroll catalog: where each scroll's CT volume and surface prediction live on the open-data bucket.

Two sources are understood:

* the data-browser index that scrollprize.org is built from (``static/data_browser/index.json`` in
  github.com/ScrollPrize/villa); a snapshot from 31 October 2026 ships with this package;
* the live open-data ``metadata.json`` at the bucket root, with surface predictions discovered by
  listing ``<scroll>/representations/predictions/surfaces/`` (use ``Catalog.load(live=True)``).
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .zarrhttp import BUCKET_HTTPS, _get

METADATA_URL = f"{BUCKET_HTTPS}/metadata.json"
BUCKET_S3 = "s3://vesuvius-challenge-open-data"


@dataclass
class Volume:
    """One CT volume: its scroll and id, voxel size (um), beam energy (keV), and the addresses of the CT and of
    its surface prediction (None if there is none).
    """
    scroll: str
    volume: str
    voxel_um: float
    energy_kev: float | None
    ct: str
    surface: str | None


def _bundled(name: str) -> Path:
    return Path(str(resources.files("scrollscout") / "data" / name))


def list_prefixes(prefix: str) -> list[str]:
    """Sub-folders of a bucket prefix (anonymous S3 ListObjectsV2)."""
    raw = _get(f"{BUCKET_HTTPS}/?list-type=2&prefix={prefix}&delimiter=/")
    if raw is None:
        return []
    return re.findall(r"<Prefix>([^<]+/)</Prefix>", raw.decode())[1:]  # first match is the query prefix


def discover_surface(scroll: str, volume_id: str) -> str | None:
    """Newest published m7 surface prediction for a volume, found by listing the bucket."""
    found = [p for p in list_prefixes(f"{scroll}/representations/predictions/surfaces/")
             if p.rstrip("/").split("/")[-1].startswith(volume_id) and p.rstrip("/").endswith(".zarr")
             and "surface-m7" in p]
    return f"{BUCKET_S3}/{sorted(found)[-1].rstrip('/')}" if found else None


class Catalog:
    """The scrolls and volumes of the open data, from the bundled snapshot, a catalog file, or the live
    metadata.json.
    """
    def __init__(self, data: dict):
        self._index = {}
        self._live = {}
        if "scrolls" in data:
            self._index = {s["id"]: s for s in data["scrolls"]}
        elif "samples" in data:
            self._live = data["samples"]
        else:
            raise ValueError("unrecognised catalog format")

    @classmethod
    def load(cls, path: str | Path | None = None, live: bool = False) -> "Catalog":
        """Read a catalog: a file (data-browser index.json or open-data metadata.json, gzipped or not), the live
        open-data metadata, or by default the bundled 31 October 2026 snapshot.
        """
        if path:
            raw = Path(path).read_bytes()
        elif live:
            raw = _get(METADATA_URL)
            if raw is None:
                raise RuntimeError("could not download the open-data metadata.json")
        else:
            raw = _bundled("catalog_index_2026-10-31.json").read_bytes()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return cls(json.loads(raw))

    def scrolls(self) -> list[str]:
        """Ids of the scrolls in the catalog."""
        return sorted(self._index or self._live)

    def volumes(self, scroll: str) -> list[str]:
        """Ids of the scroll's CT volumes."""
        if self._index:
            s = self._index.get(scroll, {})
            ids = [c["id"] for c in s.get("ctVolumes", [])]
            ids += [v["id"] for sc in s.get("scans", []) for v in sc.get("volumes", [])]
            return sorted(set(ids))
        return sorted(self._live.get(scroll, {}).get("volumes", {}))

    def volume(self, scroll: str, volume_id: str) -> Volume:
        """The Volume with this id (KeyError if the scroll has none)."""
        if self._index:
            return self._volume_from_index(scroll, volume_id)
        return self._volume_from_live(scroll, volume_id)

    def _volume_from_index(self, scroll: str, volume_id: str) -> Volume:
        s = self._index[scroll]
        ct = voxel = energy = None
        for c in s.get("ctVolumes", []):
            if c["id"] == volume_id:
                ct, voxel, energy = c["zarr"], c["px"], c.get("energy")
        if ct is None:
            for sc in s.get("scans", []):
                for v in sc.get("volumes", []):
                    if v["id"] == volume_id:
                        ct, voxel, energy = v["zarr"], sc.get("px"), sc.get("energy")
        if ct is None:
            raise KeyError(f"{scroll}: no volume {volume_id}")
        surface = None
        for p in s.get("predictions", []):
            if p.get("purpose") == "surface-prediction" and p.get("baseVolume") == volume_id:
                surface = p["zarr"]
        return Volume(scroll, volume_id, float(voxel), energy, ct, surface)

    def _volume_from_live(self, scroll: str, volume_id: str) -> Volume:
        v = self._live[scroll]["volumes"][volume_id]
        props = v.get("properties") or {}
        ct = f"{BUCKET_S3}/{scroll}/volumes/{v['long_id']}"
        return Volume(scroll, volume_id, float(props.get("pixel_size_um")), props.get("energy_keV"), ct,
                      discover_surface(scroll, volume_id))
