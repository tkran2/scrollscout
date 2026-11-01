"""How stable is the scroll ranking? Compare the v0.1 atlas (64 points per scroll, v0.1 feature code) with
the current one (128 points, faster feature code).

    python -I scripts/atlas_stability.py
"""

from __future__ import annotations

import json
from pathlib import Path

from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]


def load(d: Path) -> dict:
    out = {}
    for f in d.glob("PHerc*.json"):
        s = json.loads(f.read_text())["summary"]
        out[s["scroll"]] = s
    return out


def main():
    old, new = load(ROOT / "atlas" / "v0.1-64points"), load(ROOT / "atlas")
    keys = sorted(set(old) & set(new))
    res = {"n_scrolls": len(keys)}
    for k in ("frac_clean", "score_p90", "score_median"):
        res[k] = float(spearmanr([old[s][k] for s in keys], [new[s][k] for s in keys]).statistic)
    (ROOT / "results" / "atlas_stability.json").write_text(json.dumps(res, indent=1))
    print(res)


if __name__ == "__main__":
    main()
