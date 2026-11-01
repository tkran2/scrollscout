"""Minimal, dependency-light reader for the Vesuvius Challenge OME-Zarr volumes over HTTPS.

The open-data bucket stores every scan and prediction as zarr v2 arrays, one object per chunk,
under ``https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/<scroll>/...``.
This module reads arbitrary sub-regions of those arrays, fetching only the chunks it needs,
in parallel, with an on-disk chunk cache so repeated runs cost nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

BUCKET_HTTPS = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"

_session_local = threading.local()


def _session() -> requests.Session:
    s = getattr(_session_local, "s", None)
    if s is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=3)
        s.mount("https://", adapter)
        _session_local.s = s
    return s


def to_https(url: str) -> str:
    """Turn an ``s3://vesuvius-challenge-open-data/...`` URL into its public HTTPS form."""
    url = url.rstrip("/")
    prefix = "s3://vesuvius-challenge-open-data/"
    if url.startswith(prefix):
        return f"{BUCKET_HTTPS}/{url[len(prefix):]}"
    return url


def default_cache_dir() -> Path:
    return Path(os.environ.get("SCROLLSCOUT_CACHE", Path.home() / ".cache" / "scrollscout"))


def _get(url: str, timeout: float = 60.0) -> bytes | None:
    for attempt in range(4):
        try:
            r = _session().get(url, timeout=timeout)
        except requests.RequestException:
            if attempt == 3:
                raise
            continue
        if r.status_code == 200:
            return r.content
        if r.status_code in (403, 404):
            return None  # missing chunk: zarr fill value
        if attempt == 3:
            r.raise_for_status()
    return None


@dataclass
class ZArray:
    """One resolution level of an OME-Zarr store (a zarr v2 array)."""

    url: str
    shape: tuple[int, ...]
    chunks: tuple[int, ...]
    dtype: np.dtype
    fill_value: float
    compressor: dict | None
    sep: str
    cache_dir: Path

    @classmethod
    def open(cls, store_url: str, level: int | str = 0, cache_dir: Path | None = None) -> "ZArray":
        base = f"{to_https(store_url)}/{level}"
        meta_raw = _get(f"{base}/.zarray")
        if meta_raw is None:
            raise FileNotFoundError(f"no .zarray at {base}")
        meta = json.loads(meta_raw)
        cache_dir = Path(cache_dir or default_cache_dir())
        key = hashlib.sha1(base.encode()).hexdigest()[:16]
        return cls(
            url=base,
            shape=tuple(meta["shape"]),
            chunks=tuple(meta["chunks"]),
            dtype=np.dtype(meta["dtype"]),
            fill_value=meta.get("fill_value") or 0,
            compressor=meta.get("compressor"),
            sep=meta.get("dimension_separator", "."),
            cache_dir=cache_dir / key,
        )

    # ------------------------------------------------------------------ chunks
    def _decode(self, raw: bytes) -> np.ndarray:
        if self.compressor:
            from numcodecs import get_codec

            raw = get_codec(self.compressor).decode(raw)
        arr = np.frombuffer(raw, dtype=self.dtype)
        return arr.reshape(self.chunks)

    def chunk(self, idx: tuple[int, ...]) -> np.ndarray | None:
        """Return one decoded chunk, or None if it is absent (all fill value)."""
        name = self.sep.join(str(i) for i in idx)
        path = self.cache_dir / name.replace("/", "_")
        if path.exists():
            raw = path.read_bytes()
            if raw == b"":
                return None
        else:
            raw = _get(f"{self.url}/{name}")
            if not os.environ.get("SCROLLSCOUT_NO_CACHE"):
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_bytes(raw or b"")
                tmp.replace(path)
            if raw is None:
                return None
        return self._decode(raw)

    # ------------------------------------------------------------------ regions
    def read(self, z0: int, z1: int, y0: int, y1: int, x0: int, x1: int, workers: int = 16) -> np.ndarray:
        """Read the box [z0:z1, y0:y1, x0:x1] (clipped to the array) into memory."""
        lo = [max(0, v) for v in (z0, y0, x0)]
        hi = [min(s, v) for s, v in zip(self.shape, (z1, y1, x1))]
        out = np.full([max(0, h - l) for l, h in zip(lo, hi)], self.fill_value, dtype=self.dtype)
        if out.size == 0:
            return out
        ranges = [range(l // c, (h - 1) // c + 1) for l, h, c in zip(lo, hi, self.chunks)]
        idxs = [(a, b, c) for a in ranges[0] for b in ranges[1] for c in ranges[2]]

        def load(idx):
            return idx, self.chunk(idx)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for idx, data in pool.map(load, idxs):
                if data is None:
                    continue
                src, dst = [], []
                for d in range(3):
                    c0 = idx[d] * self.chunks[d]
                    a = max(lo[d], c0)
                    b = min(hi[d], c0 + self.chunks[d])
                    src.append(slice(a - c0, b - c0))
                    dst.append(slice(a - lo[d], b - lo[d]))
                out[tuple(dst)] = data[tuple(src)]
        return out

    def read_centered(self, center_zyx, half: int, **kw) -> np.ndarray:
        z, y, x = (int(round(v)) for v in center_zyx)
        return self.read(z - half, z + half, y - half, y + half, x - half, x + half, **kw)
