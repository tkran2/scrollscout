"""Labels from the First Letters survey (github.com/Bullo27/first-letters-survey).

The survey grew 65 patches with VC3D's GrowPatch tracer on the scrolls eligible for the First
Letters prizes and described, by eye, whether each surface stayed on one papyrus sheet. Those
verdicts are the ground truth we validate against: a good seed is one whose patch followed the
sheet.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

GOOD, MOSTLY, PARTIAL, BAD = 3, 2, 1, 0
LABEL_NAMES = {GOOD: "follows the sheet throughout", MOSTLY: "follows it over most of the patch",
               PARTIAL: "on the sheet in parts", BAD: "swirls / leaves the papyrus"}


def label_from_verdict(text: str) -> int:
    """Map the survey's free-text surface verdict to an ordinal label (3 best .. 0 worst)."""
    t = text.lower()
    on_sheet = re.search(r"(follows the sheet|on the sheet|on-sheet|partly on|crosshatch)", t)
    if "follows the sheet throughout" in t:
        return GOOD
    if re.search(r"(over most of the patch|right two-thirds)", t) and re.search(r"(follows the sheet|on the sheet)", t):
        return MOSTLY
    if on_sheet:
        return PARTIAL
    return BAD


def load_patches(results_json: str | Path) -> list[dict]:
    r = json.loads(Path(results_json).read_text())
    rows = []
    for p in r["patches"]:
        verdict = p["visual_qa"]["surface"]
        rows.append(
            {
                "scroll": p["scroll"],
                "volume": p["volume"],
                "pass": p["pass"],
                "voxel_um": p["voxel_um"],
                "seed_zyx": (p["seed"]["z"], p["seed"]["y"], p["seed"]["x"]),
                "r_frac": p.get("seed_placement", {}).get("r_frac_measured"),
                "area_cm2": float(p["area_cm2"]),
                "verdict": verdict,
                "label": label_from_verdict(verdict),
                "tifxyz": p.get("tifxyz"),
            }
        )
    return rows
