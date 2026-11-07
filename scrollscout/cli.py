"""Command line: ``scrollscout point | scan | near | seeds | export-vc3d | check-segment | atlas``."""

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


def _progress(a):
    """Where per-point progress goes: stderr, or nowhere with --quiet."""
    return None if a.quiet else _log


def _positive(text: str) -> int:
    """argparse type: a whole number of at least 1."""
    try:
        v = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if v < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {v}")
    return v


def _warn_scan(vol):
    from .scout import validated_scan

    if not validated_scan(vol):
        _log(f"note: {vol.scroll} {vol.volume} is a {vol.voxel_um} um scan; the score was validated on 8.64 and "
             f"9.36 um scans only, so treat its numbers with caution")


def cmd_point(a):
    from .scout import features_at

    vol = _catalog(a).volume(a.scroll, a.volume)
    _warn_scan(vol)
    feats = features_at(vol, (a.z, a.y, a.x))
    cal = _calibration(a.calibration)
    score = cal.score(feats)
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.5)
    print(json.dumps({"scroll": a.scroll, "volume": a.volume, "xyz": [a.x, a.y, a.z], "score": score,
                      "verdict": "clean (good seed)" if score > thr else "doubtful", "features": feats}, indent=1))


def cmd_scan(a):
    from .atlas import scan_volume, seed_commands

    vol = _catalog(a).volume(a.scroll, a.volume)
    _warn_scan(vol)
    res = scan_volume(vol, _calibration(a.calibration), a.points, a.workers, log=_progress(a))
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


def cmd_export_vc3d(a):
    from .vc3d import to_point_collections

    res = json.loads(Path(a.file).read_text())
    thr = _calibration(a.calibration).stats.get("_good_threshold", {}).get("value", 0.63)
    doc = to_point_collections(res, thr)
    out = Path(a.out or Path(a.file).with_suffix(".vc3d_points.json"))
    out.write_text(json.dumps(doc, indent=1))
    n = {c["name"]: len(c["points"]) for c in doc["collections"].values()}
    print(f"wrote {out}: " + ", ".join(f"{k.split(': ', 1)[1]} {v}" for k, v in n.items()))


def cmd_near(a):
    from .atlas import scan_near, seed_commands

    vol = _catalog(a).volume(a.scroll, a.volume)
    _warn_scan(vol)
    cal = _calibration(a.calibration)
    res = scan_near(vol, cal, (a.z, a.y, a.x), a.step, a.size, a.workers, log=_progress(a))
    s = res["summary"]
    thr = cal.stats.get("_good_threshold", {}).get("value", 0.63)
    out = Path(a.out or f"{a.scroll}_{a.volume}_near_{a.x}_{a.y}_{a.z}.json")
    out.write_text(json.dumps(res, indent=1, default=float))
    mm = vol.voxel_um / 1000
    ts = s["target_score"]
    where = "" if s["target_in_papyrus"] else " (outside the papyrus in the coarse CT)"
    if np.isfinite(ts):
        print(f"target x={a.x} y={a.y} z={a.z}{where}: score {ts:+.2f}, "
              f"{'clean' if ts > thr else 'doubtful'} (clean above {thr:.2f})")
    else:
        print(f"target x={a.x} y={a.y} z={a.z}{where}: could not be scored (no papyrus or outside the scan)")
    print(f"best of {s['n_points']} points within {a.step * (a.size - 1) / 2 * 3 ** 0.5 * mm:.1f} mm "
          f"(x y z, level-0 voxels):")
    for i, sd in enumerate(s["seeds"], 1):
        x, y, z = sd["xyz"]
        print(f"{i}. x={x} y={y} z={z}  score {sd['score']:+.2f}  {sd['dist_vox'] * mm:.1f} mm from the target")
    print("# grow a patch from each (github.com/Bullo27/first-letters-survey):")
    print("\n".join(seed_commands(s)))
    print(f"all points -> {out}  (scrollscout export-vc3d {out} for VC3D)")


def _check_one(src, a, cat, cal, multi):
    from .segment import check_segment, infer_volume, load_surface, plot_check, to_point_collections

    surf = load_surface(src)
    vol = infer_volume(surf, cat, a.scroll, a.volume)
    if vol.surface is None:
        raise ValueError(f"{vol.scroll} {vol.volume}: no published surface prediction to check against")
    _warn_scan(vol)
    _log(f"{surf.name}: {len(surf.zyx):,} nodes on {vol.scroll} {vol.volume} ({vol.voxel_um} um); "
         f"scoring {min(a.points, len(surf.zyx))} points")
    res = check_segment(surf, vol, cal, a.points, a.workers, log=_progress(a))
    s = res["summary"]
    print(f"{s['segment']}: {s['verdict'].upper()}")
    if s["errors"]:
        print(f"  could not score {len(res['points']) - s['n_points']} point(s): {s['errors'][0]}")
    if s["n_points"]:
        n_clean = round(s["frac_clean"] * s["n_points"])
        print(f"  median score {s['median_score']:+.2f} (clean above {s['threshold']:.2f}); "
              f"{n_clean} of {s['n_points']} scored points clean")
    if s["trouble_spots"]:
        print("  crushed papyrus (score < 0) at x y z: " + "; ".join(" ".join(map(str, p)) for p in s["trouble_spots"][:6]))
    if s["no_papyrus"]:
        print(f"  no papyrus in the CT around {len(s['no_papyrus'])} of {len(res['points'])} points (the segment leaves "
              "the scroll or the scan there): " + "; ".join(" ".join(map(str, p)) for p in s["no_papyrus"][:6]))

    def target(opt, suffix):  # with several segments, each output option names a folder
        if not opt:
            return None
        if not multi:
            return Path(opt)
        Path(opt).mkdir(parents=True, exist_ok=True)
        return Path(opt) / f"{s['segment']}{suffix}"

    if (f := target(a.json, ".json")):
        f.write_text(json.dumps(res, indent=1, default=float))
        print(f"  details -> {f}")
    if (f := target(a.png, ".png")):
        plot_check(surf, res, f)
        print(f"  map -> {f}")
    if (f := target(a.vc3d, ".vc3d_points.json")):
        f.write_text(json.dumps(to_point_collections(res), indent=1))
        print(f"  VC3D point collections -> {f}")
    return s


def cmd_check_segment(a):
    import csv

    cat, cal = _catalog(a), _calibration(a.calibration)
    multi = len(a.segment) > 1
    done = []
    for src in a.segment:
        try:
            done.append(_check_one(src, a, cat, cal, multi))
        except (ValueError, FileNotFoundError, KeyError, OSError) as e:
            if not multi:
                raise SystemExit(f"{src}: {e}")
            print(f"{src}: skipped ({e})")
    if multi and done:
        print(f"\n{'segment':<48}{'median':>8}{'clean':>7}  verdict")
        for s in sorted(done, key=lambda s: -np.nan_to_num(s["median_score"], nan=-9)):
            print(f"{s['segment'][:47]:<48}{s['median_score']:>+8.2f}{s['frac_clean']:>7.0%}  {s['verdict']}")
        follows = sum(s["verdict"].endswith("follows the sheet") for s in done)
        print(f"{follows} of {len(done)} likely follow their sheet")
    if a.csv and done:
        cols = ["segment", "scroll", "volume", "verdict", "median_score", "frac_clean", "n_points", "n_nodes", "area_cm2"]
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols + ["no_papyrus"], extrasaction="ignore")
            w.writeheader()
            for s in done:
                w.writerow({**s, "no_papyrus": len(s["no_papyrus"])})
        print(f"summary -> {a.csv}")
    if a.fail_on_cross:
        bad = len(a.segment) - sum(s["verdict"].endswith("follows the sheet") for s in done)
        if bad:
            raise SystemExit(f"check failed: {bad} of {len(a.segment)} segment(s) not likely to follow the sheet")


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
            res = scan_volume(cat.volume(e["scroll"], e["volume"]), cal, a.points, a.workers, log=_progress(a))
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
                                 "clean enough to trace, and check whether traced segments stay on their sheet, "
                                 "from public CT data, on a laptop CPU.")
    from . import __version__

    ap.add_argument("--version", action="version", version=f"scrollscout {__version__}")
    ap.add_argument("--catalog", help="catalog file (data-browser index.json or open-data metadata.json)")
    ap.add_argument("--live", action="store_true", help="use the live open-data catalog instead of the bundled snapshot")
    ap.add_argument("--calibration", help="calibration.json (default: bundled)")
    ap.add_argument("-q", "--quiet", action="store_true", help="hide the per-point progress lines")
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
    p.add_argument("--points", type=_positive, default=64)
    p.add_argument("--workers", type=_positive, default=4)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("seeds", help="print the seeds of a scan result and commands to grow patches there")
    p.add_argument("file")
    p.add_argument("--top", type=_positive, default=5)
    p.set_defaults(fn=cmd_seeds)

    p = sub.add_parser("export-vc3d", help="write a scan result as a VC3D point-collections file (colour-coded points and seeds)")
    p.add_argument("file")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_export_vc3d)

    p = sub.add_parser("near", help="find the cleanest seeds around a target point, e.g. where text was seen")
    p.add_argument("scroll")
    p.add_argument("volume")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)
    p.add_argument("--step", type=_positive, default=300, help="grid spacing in level-0 voxels (default 300)")
    p.add_argument("--size", type=_positive, default=3, help="points per side of the grid (default 3: 27 points)")
    p.add_argument("--workers", type=_positive, default=4)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_near)

    p = sub.add_parser("check-segment", help="check a traced segment (tifxyz folder, OBJ, or open-data URL) "
                       "before ink detection: does it follow the sheet, and where does it run into crushed papyrus?")
    p.add_argument("segment", nargs="+", help="tifxyz folder(s), .obj file(s), or s3:// / https:// segment folders "
                   "in the open data (several at once: e.g. a VC3D paths/* folder)")
    p.add_argument("--scroll", help="e.g. PHerc0800 (inferred from the path when it names the scroll)")
    p.add_argument("--volume", help="CT volume id the segment was traced on (inferred from meta.json or the path)")
    p.add_argument("--points", type=_positive, default=12, help="points to score, spread over the surface (default 12)")
    p.add_argument("--workers", type=_positive, default=4)
    p.add_argument("--json", help="write every point's score and features here (a folder, with several segments)")
    p.add_argument("--png", help="draw a map of the segment coloured by score, needs matplotlib (a folder, with "
                   "several segments)")
    p.add_argument("--vc3d", help="write the scored points as VC3D point collections (a folder, with several segments)")
    p.add_argument("--csv", help="write one summary row per segment here")
    p.add_argument("--fail-on-cross", action="store_true", help="exit with status 1 unless every segment likely "
                   "follows the sheet (to stop a pipeline before ink detection)")
    p.set_defaults(fn=cmd_check_segment)

    p = sub.add_parser("atlas", help="scan every volume eligible for a prize and rank them")
    p.add_argument("--prize", default="first-letters-2027")
    p.add_argument("--eligibility", help="prizeEligibility.json (default: bundled 31 Oct 2026 snapshot)")
    p.add_argument("--points", type=_positive, default=64)
    p.add_argument("--workers", type=_positive, default=4)
    p.add_argument("--out", default="atlas")
    p.set_defaults(fn=cmd_atlas)

    a = ap.parse_args(argv)
    np.seterr(all="ignore")
    a.fn(a)


if __name__ == "__main__":
    main()
