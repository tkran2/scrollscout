"""Command line: ``scrollscout point | scan | seeds | atlas``."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

import numpy as np


def _calibration(path=None):
    from .scout import Calibration

    return Calibration.load(path or Path(str(resources.files("scrollscout") / "data" / "calibration.json")))


def _catalog(a):
    from .catalog import Catalog

    return Catalog.load(a.catalog, live=a.live)


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def cmd_point(a):
    from .scout import features_at

    vol = _catalog(a).volume(a.scroll, a.volume)
    feats = features_at(vol, (a.z, a.y, a.x))
    cal = _calibration(a.calibration)
    score = cal.score(feats)
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.5)
    print(json.dumps({"scroll": a.scroll, "volume": a.volume, "xyz": [a.x, a.y, a.z], "score": score,
                      "verdict": "clean (good seed)" if score > thr else "doubtful", "features": feats}, indent=1))


def cmd_scan(a):
    from .atlas import scan_volume, seed_commands

    vol = _catalog(a).volume(a.scroll, a.volume)
    res = scan_volume(vol, _calibration(a.calibration), a.points, a.workers, log=_log)
    out = Path(a.out or f"{a.scroll}_{a.volume}_scout.json")
    out.write_text(json.dumps(res, indent=1, default=float))
    s = res["summary"]
    print(f"{a.scroll}: median score {s['score_median']:.2f}, best 10% {s['score_p90']:.2f}, "
          f"clean {s['frac_clean']:.0%} -> {out}")
    print("\n".join(seed_commands(s)))


def cmd_seeds(a):
    from .atlas import inner_seeds, seed_commands

    res = json.loads(Path(a.file).read_text())
    s = res["summary"]
    lists = [("top seeds anywhere", s["seeds"][: a.top])]
    if res.get("points"):
        inner = [{"zyx": p["zyx"], "xyz": p["zyx"][::-1], "score": p["score"], "r_frac": p["r_frac"],
                  "z_frac": p["z_frac"]} for p in inner_seeds(res["points"], k=a.top)]
        lists.append(("top seeds in the inner zone (where known text finds lie)", inner))
    for title, seeds in lists:
        print(f"# {s['scroll']} volume {s['volume']} ({s['voxel_um']} um): {title} (x y z, level-0 voxels)")
        for i, sd in enumerate(seeds, 1):
            x, y, z = sd["xyz"]
            print(f"{i}. x={x} y={y} z={z}  score {sd['score']:.2f}  radius {sd['r_frac']:.2f}  height {sd['z_frac']:.2f}")
        print("# grow a patch from each (github.com/Bullo27/first-letters-survey):")
        print("\n".join(seed_commands({"scroll": s["scroll"], "seeds": seeds}, a.top)))
        print()


def cmd_atlas(a):
    from .atlas import scan_volume

    cat = _catalog(a)
    cal = _calibration(a.calibration)
    elig = json.loads(Path(a.eligibility or str(resources.files("scrollscout") / "data" /
                                                "prize_eligibility_2026-10-31.json")).read_text())[a.prize]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for e in elig:
        dst = out / f"{e['scroll']}.json"
        if dst.exists():
            res = json.loads(dst.read_text())
        else:
            res = scan_volume(cat.volume(e["scroll"], e["volume"]), cal, a.points, a.workers, log=_log)
            dst.write_text(json.dumps(res, indent=1, default=float))
        rows.append(res["summary"])
    rows.sort(key=lambda s: -s["score_p90"])
    print(f"{'scroll':<12}{'um':>7}{'median':>8}{'best10%':>9}{'clean':>7}  best seed (x y z)")
    for s in rows:
        x, y, z = s["seeds"][0]["xyz"] if s["seeds"] else ("-", "-", "-")
        print(f"{s['scroll']:<12}{s['voxel_um']:>7.2f}{s['score_median']:>8.2f}{s['score_p90']:>9.2f}"
              f"{s['frac_clean']:>7.0%}  {x} {y} {z}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scrollscout", description="Find where Herculaneum scroll papyrus is "
                                 "clean enough to trace, from public CT data, on a laptop CPU.")
    ap.add_argument("--catalog", help="catalog file (data-browser index.json or open-data metadata.json)")
    ap.add_argument("--live", action="store_true", help="use the live open-data catalog instead of the bundled snapshot")
    ap.add_argument("--calibration", help="calibration.json (default: bundled)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("point", help="score one point (level-0 voxel coordinates)")
    p.add_argument("scroll")
    p.add_argument("volume")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)
    p.set_defaults(fn=cmd_point)

    p = sub.add_parser("scan", help="sample and score points through one scroll volume, pick seeds")
    p.add_argument("scroll")
    p.add_argument("volume")
    p.add_argument("--points", type=int, default=64)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("seeds", help="print the seeds of a scan result and commands to grow patches there")
    p.add_argument("file")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(fn=cmd_seeds)

    p = sub.add_parser("atlas", help="scan every volume eligible for a prize and rank them")
    p.add_argument("--prize", default="first-letters-2027")
    p.add_argument("--eligibility", help="prizeEligibility.json (default: bundled 31 Oct 2026 snapshot)")
    p.add_argument("--points", type=int, default=64)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="atlas")
    p.set_defaults(fn=cmd_atlas)

    a = ap.parse_args(argv)
    np.seterr(all="ignore")
    a.fn(a)


if __name__ == "__main__":
    main()
