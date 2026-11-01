"""Export scout results as a VC3D point-collections file.

VC3D keeps point annotations in a JSON document (``vc_pointcollections_json_version`` "1", the format
read by ``PointCollections::loadFromJSON`` in volume-cartographer). Each scored sample point goes into a
colour-coded collection (clean / middling / crushed) and the recommended seeds into their own
collections, so the scout's view of a scroll can sit next to the CT in VC3D. Coordinates are level-0
voxels ``[x, y, z]`` of the scanned volume, the same frame as VC3D's own points.
"""

from __future__ import annotations

import time
import uuid

import numpy as np

from .atlas import inner_seeds

GREEN, YELLOW, RED, ORANGE, BLUE = [0.05, 0.64, 0.05], [0.98, 0.70, 0.10], [0.82, 0.23, 0.23], \
    [0.92, 0.41, 0.20], [0.16, 0.47, 0.84]


def collections_doc(groups) -> dict:
    """``groups`` is a list of (name, colour, points); each point has ``zyx`` in level-0 voxels."""
    now = int(time.time())
    collections = {}
    for cid, (name, color, members) in enumerate(groups):
        points = {}
        for pid, p in enumerate(members):
            z, y, x = p["zyx"]
            points[str(pid)] = {"p": [float(x), float(y), float(z)], "creation_time": now}
        collections[str(cid)] = {
            "uuid": str(uuid.uuid4()),
            "name": name,
            "points": points,
            "metadata": {},
            "color": color,
        }
    return {"vc_pointcollections_json_version": "1", "collections": collections}


def to_point_collections(scan: dict, clean_threshold: float = 0.63) -> dict:
    s = scan["summary"]
    pts = [p for p in scan.get("points", []) if np.isfinite(p.get("score", np.nan))]
    return collections_doc([
        (f"scout {s['scroll']}: clean (score > {clean_threshold:.2f})", GREEN, [p for p in pts if p["score"] > clean_threshold]),
        (f"scout {s['scroll']}: middling (0 to {clean_threshold:.2f})", YELLOW,
         [p for p in pts if 0 <= p["score"] <= clean_threshold]),
        (f"scout {s['scroll']}: crushed (score < 0)", RED, [p for p in pts if p["score"] < 0]),
        (f"scout {s['scroll']}: recommended seeds, inner zone", ORANGE, inner_seeds(pts, k=5) if pts else []),
        (f"scout {s['scroll']}: recommended seeds, anywhere", BLUE, s.get("seeds", [])),
    ])
