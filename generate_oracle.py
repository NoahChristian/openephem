#!/usr/bin/env python3
"""
generate_oracle.py — Swiss Ephemeris reference-data (oracle) generator.

Purpose
-------
Produce a "golden" dataset of astronomical positions from Swiss Ephemeris so a
permissively-licensed replacement engine (Moshier is the first candidate) can be
validated against it for parity.

Licensing hygiene (read this)
-----------------------------
  * Run this OFFLINE, as a build/test step. It uses pyswisseph (AGPL) purely to
    *generate numbers*. Computed planetary positions are astronomical FACTS and
    are not copyrightable, so committing the resulting fixtures is clean.
  * DO NOT vendor swisseph source or the .se1 data files into the app repo.
    Keep this generator + the .se1 files OUT of the product; commit only the
    emitted JSON/CSV fixtures.
  * The replacement engine that ships in production must be the permissive one
    (e.g. Moshier / astronomy-engine), never swisseph, unless you hold the
    Astrodienst Professional License.

Moshier-first strategy
----------------------
swisseph itself has a data-file-free "Moshier" mode (FLG_MOSEPH). Before porting
a standalone Moshier engine, we can quantify Moshier-vs-Swiss error *through the
same API* by computing every body in BOTH modes and diffing them. That gives an
immediate, honest read on whether Moshier is accurate enough for your readings —
and it exposes the Chiron problem directly (Moshier mode cannot do asteroids).

Usage
-----
    pip install pyswisseph
    python generate_oracle.py --start 1950 --end 2100 --step-days 7 \
        --ephe-path /path/to/ephe --out ./fixtures

    # add sign-ingress boundary cases (the interpretation-critical ones):
    python generate_oracle.py --boundaries

Outputs (in --out dir)
----------------------
    oracle.json        full records: Swiss (authority) + Moshier + houses + meta
    deltas.csv         per-(instant,body) Swiss-vs-Moshier delta + sign-flip flag
    summary printed to stdout (max/mean arcsec error, sign-flip count, gaps)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict

try:
    import swisseph as swe
except ImportError:
    sys.exit(
        "pyswisseph not installed. Run:  pip install pyswisseph\n"
        "(This is only needed to GENERATE the oracle, never to ship it.)"
    )

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# House systems to snapshot. byte code -> label. (Placidus/Koch degrade at high
# latitude — the runner should tolerate that; Whole Sign / Equal are robust.)
HOUSE_SYSTEMS = {
    b"P": "Placidus",
    b"K": "Koch",
    b"W": "WholeSign",
    b"E": "Equal",
    b"R": "Regiomontanus",
    b"C": "Campanus",
}

# Reference location for house/Asc/MC math (houses need an observer).
# Default: London. Override per your customer base if you like.
DEFAULT_GEO = {"name": "London", "lat": 51.5074, "lon": -0.1278}


@dataclass(frozen=True)
class Body:
    name: str
    ipl: int
    moshier: bool  # available in FLG_MOSEPH mode?


def build_body_table() -> list[Body]:
    """Standard natal/transit bodies. `moshier=False` => NOT computable in
    Moshier mode (asteroids need .se1 data), which is exactly the feasibility
    gate for a Moshier-only replacement."""
    return [
        Body("Sun", swe.SUN, True),
        Body("Moon", swe.MOON, True),
        Body("Mercury", swe.MERCURY, True),
        Body("Venus", swe.VENUS, True),
        Body("Mars", swe.MARS, True),
        Body("Jupiter", swe.JUPITER, True),
        Body("Saturn", swe.SATURN, True),
        Body("Uranus", swe.URANUS, True),
        Body("Neptune", swe.NEPTUNE, True),
        Body("Pluto", swe.PLUTO, True),
        Body("MeanNode", swe.MEAN_NODE, True),
        Body("TrueNode", swe.TRUE_NODE, True),
        Body("MeanLilith", swe.MEAN_APOG, True),
        Body("OscuLilith", swe.OSCU_APOG, True),
        # --- asteroids: need seas_*.se1 (Swiss) or a JPL SPK kernel; Moshier can't.
        #     These map 1:1 to the Skyfield SPK asteroid engine (asteroids_skyfield.py).
        Body("Chiron", swe.CHIRON, False),
        Body("Ceres", swe.CERES, False),
        Body("Pallas", swe.PALLAS, False),
        Body("Juno", swe.JUNO, False),
        Body("Vesta", swe.VESTA, False),
    ]


# --------------------------------------------------------------------------- #
# Math helpers
# --------------------------------------------------------------------------- #

def angular_sep_deg(a: float, b: float) -> float:
    """Smallest separation between two ecliptic longitudes, in degrees."""
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def deg_to_arcsec(d: float) -> float:
    return d * 3600.0


def zodiac_sign(lon: float) -> str:
    return SIGNS[int(lon % 360.0 // 30.0)]


def sign_and_degree(lon: float) -> str:
    lon %= 360.0
    return f"{zodiac_sign(lon)} {lon % 30.0:05.2f}"


# --------------------------------------------------------------------------- #
# Swiss Ephemeris wrappers
# --------------------------------------------------------------------------- #

FLAGS_BASE = swe.FLG_SPEED  # always want speed (retrograde/station detection)


def compute_body(jd_ut: float, body: Body, mode_flag: int) -> dict | None:
    """Return position dict for one body in one ephemeris mode, or None (with a
    recorded reason) if unavailable in that mode."""
    flags = FLAGS_BASE | mode_flag
    try:
        xx, retflag = swe.calc_ut(jd_ut, body.ipl, flags)
    except swe.Error as exc:  # e.g. missing asteroid .se1 file in a given mode
        return {"error": str(exc)}
    lon, lat, dist, lon_speed, lat_speed, dist_speed = xx
    result = {
        "lon": lon,
        "lat": lat,
        "dist_au": dist,
        "lon_speed": lon_speed,          # deg/day; sign<0 => retrograde
        "retrograde": lon_speed < 0.0,
        "sign": zodiac_sign(lon),
        "position": sign_and_degree(lon),
        "retflag": retflag,
    }
    # Equatorial RA/Dec too — needed for declination aspects (parallel/
    # contraparallel), out-of-bounds, and paran work. Candidate must match these.
    try:
        eq, _ = swe.calc_ut(jd_ut, body.ipl, flags | swe.FLG_EQUATORIAL)
        result["ra"] = eq[0]
        result["dec"] = eq[1]
    except swe.Error:
        pass
    return result


def compute_houses(jd_ut: float, geo: dict) -> dict:
    out = {}
    for code, label in HOUSE_SYSTEMS.items():
        try:
            cusps, ascmc = swe.houses(jd_ut, geo["lat"], geo["lon"], code)
            out[label] = {
                "cusps": list(cusps),
                "asc": ascmc[0],
                "mc": ascmc[1],
                "armc": ascmc[2],        # right ascension of MC (sidereal time)
                "vertex": ascmc[3],
                "east_point": ascmc[4],  # equatorial ascendant
                "asc_pos": sign_and_degree(ascmc[0]),
                "mc_pos": sign_and_degree(ascmc[1]),
            }
        except swe.Error as exc:
            out[label] = {"error": str(exc)}
    return out


# --------------------------------------------------------------------------- #
# Instant grids
# --------------------------------------------------------------------------- #

def grid_instants(start_year: int, end_year: int, step_days: float) -> list[float]:
    """Uniform JD(UT) grid at 00:00 UT of the start, stepping by step_days."""
    jd0 = swe.julday(start_year, 1, 1, 0.0)
    jd1 = swe.julday(end_year, 1, 1, 0.0)
    n = int((jd1 - jd0) / step_days)
    return [jd0 + i * step_days for i in range(n + 1)]


def find_sign_ingresses(bodies: list[Body], start_year: int, end_year: int,
                        coarse_step_days: float = 1.0,
                        tol_days: float = 1e-4) -> list[dict]:
    """Locate zodiac-sign ingress instants by bisection. These are the
    interpretation-critical boundaries: a replacement engine that is 2" off can
    flip the sign here, changing the reading. We emit instants bracketing each
    ingress so the parity runner can assert the *categorical* result matches."""
    ingresses: list[dict] = []
    jd0 = swe.julday(start_year, 1, 1, 0.0)
    jd1 = swe.julday(end_year, 1, 1, 0.0)
    for body in bodies:
        if not body.moshier:
            continue  # only meaningful where a Moshier comparison exists
        jd = jd0
        prev = _sign_index(jd, body)
        while jd < jd1:
            nxt = jd + coarse_step_days
            cur = _sign_index(nxt, body)
            if cur is not None and prev is not None and cur != prev:
                lo, hi = jd, nxt
                while hi - lo > tol_days:  # bisection to the ingress instant
                    mid = 0.5 * (lo + hi)
                    if _sign_index(mid, body) == prev:
                        lo = mid
                    else:
                        hi = mid
                ingresses.append({
                    "body": body.name,
                    "jd_ingress": hi,
                    "from_sign": SIGNS[prev],
                    "to_sign": SIGNS[cur],
                })
            prev = cur if cur is not None else prev
            jd = nxt
    return ingresses


def _sign_index(jd_ut: float, body: Body) -> int | None:
    try:
        xx, _ = swe.calc_ut(jd_ut, body.ipl, FLAGS_BASE | swe.FLG_SWIEPH)
    except swe.Error:
        return None
    return int(xx[0] % 360.0 // 30.0)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def run(args) -> None:
    if args.ephe_path:
        swe.set_ephe_path(args.ephe_path)  # needed for Chiron + best Swiss precision

    # Authority ephemeris. Default swieph (compressed DE431). Choosing jpleph +
    # de440.bsp makes the swisseph authority use the SAME ephemeris as the
    # Skyfield+DE440 candidate, so run_parity.py's residuals are pure CONVENTION
    # differences (Δt, apparent-of-date, node/Lilith defs), not DE vintage.
    auth_flag = swe.FLG_SWIEPH
    auth_label = "FLG_SWIEPH (swisseph compressed DE431)"
    if args.authority == "jpleph":
        if args.jpl_file:
            swe.set_jpl_file(args.jpl_file)
        auth_flag = swe.FLG_JPLEPH
        auth_label = f"FLG_JPLEPH ({args.jpl_file or 'default JPL file'})"

    lib_ver = getattr(swe, "version", "unknown")
    pkg_ver = getattr(swe, "__version__", "unknown")
    bodies = build_body_table()
    geo = DEFAULT_GEO

    instants = grid_instants(args.start, args.end, args.step_days)
    boundary_instants: list[float] = []
    ingress_meta: list[dict] = []
    if args.boundaries:
        ingress_meta = find_sign_ingresses(bodies, args.start, args.end)
        eps = 1.0 / 1440.0  # +/- 1 minute around each ingress
        for ing in ingress_meta:
            boundary_instants += [ing["jd_ingress"] - eps, ing["jd_ingress"] + eps]

    all_instants = sorted(set(instants + boundary_instants))
    print(f"[oracle] swisseph lib={lib_ver} pyswisseph={pkg_ver}", file=sys.stderr)
    print(f"[oracle] instants: {len(all_instants)} "
          f"(grid={len(instants)}, boundary={len(boundary_instants)}), "
          f"bodies={len(bodies)}", file=sys.stderr)

    records = []
    delta_rows = []
    max_arcsec = 0.0
    sum_arcsec = 0.0
    cmp_count = 0
    sign_flips = 0
    moshier_gaps = 0

    for jd in all_instants:
        cal = swe.revjul(jd)  # (y, m, d, ut_hour)
        rec = {
            "jd_ut": jd,
            "utc": f"{cal[0]:04d}-{cal[1]:02d}-{cal[2]:06.3f}h{cal[3]:.4f}",
            "delta_t_sec": swe.deltat(jd) * 86400.0,
            "bodies": {},
            "houses": compute_houses(jd, geo),
        }
        for body in bodies:
            swiss = compute_body(jd, body, auth_flag)        # authority
            mosh = compute_body(jd, body, swe.FLG_MOSEPH)    # legacy Moshier ref
            entry = {"swiss": swiss, "moshier": mosh}

            swiss_ok = swiss and "lon" in swiss
            mosh_ok = mosh and "lon" in mosh
            if swiss_ok and mosh_ok:
                sep = angular_sep_deg(swiss["lon"], mosh["lon"])
                arcsec = deg_to_arcsec(sep)
                flip = swiss["sign"] != mosh["sign"]
                entry["delta_arcsec"] = arcsec
                entry["sign_flip"] = flip
                max_arcsec = max(max_arcsec, arcsec)
                sum_arcsec += arcsec
                cmp_count += 1
                sign_flips += int(flip)
                delta_rows.append({
                    "jd_ut": f"{jd:.6f}",
                    "utc": rec["utc"],
                    "body": body.name,
                    "swiss_lon": f"{swiss['lon']:.6f}",
                    "moshier_lon": f"{mosh['lon']:.6f}",
                    "delta_arcsec": f"{arcsec:.4f}",
                    "sign_flip": int(flip),
                    "swiss_pos": swiss["position"],
                    "moshier_pos": mosh["position"],
                })
            elif swiss_ok and not mosh_ok:
                # Chiron / asteroids land here: authority has it, Moshier can't.
                moshier_gaps += 1
                entry["moshier_unavailable"] = True
            rec["bodies"][body.name] = entry
        records.append(rec)

    os.makedirs(args.out, exist_ok=True)
    oracle_path = os.path.join(args.out, "oracle.json")
    deltas_path = os.path.join(args.out, "deltas.csv")

    with open(oracle_path, "w", encoding="utf-8") as fh:
        json.dump({
            "meta": {
                "generator": "generate_oracle.py",
                "swisseph_lib_version": lib_ver,
                "pyswisseph_version": pkg_ver,
                "authority_flag": auth_label,
                "legacy_moshier_ref_flag": "FLG_MOSEPH",
                "production_candidate": "Skyfield + DE440 (validated by run_parity.py)",
                "flags_base": "FLG_SPEED",
                "equatorial_ra_dec": True,
                "geo": geo,
                "house_systems": {v: k.decode() for k, v in
                                  {b: l for b, l in HOUSE_SYSTEMS.items()}.items()},
                "start_year": args.start,
                "end_year": args.end,
                "step_days": args.step_days,
                "boundaries_included": args.boundaries,
                "ingresses": ingress_meta,
                "note": "Numbers are astronomical facts; safe to commit. "
                        "Do NOT commit .se1 files or swisseph source.",
            },
            "records": records,
        }, fh, indent=2)

    with open(deltas_path, "w", encoding="utf-8", newline="") as fh:
        if delta_rows:
            writer = csv.DictWriter(fh, fieldnames=list(delta_rows[0].keys()))
            writer.writeheader()
            writer.writerows(delta_rows)

    mean_arcsec = (sum_arcsec / cmp_count) if cmp_count else 0.0
    print("\n=== Moshier-vs-Swiss parity summary ===")
    print(f"  comparisons          : {cmp_count}")
    print(f"  max longitude error  : {max_arcsec:9.3f} arcsec "
          f"({max_arcsec/60.0:.3f} arcmin)")
    print(f"  mean longitude error : {mean_arcsec:9.3f} arcsec")
    print(f"  SIGN FLIPS            : {sign_flips}  <-- interpretation-breaking")
    print(f"  Moshier gaps (Chiron): {moshier_gaps}  <-- unavailable in Moshier mode")
    print(f"\n  wrote {oracle_path}")
    print(f"  wrote {deltas_path}")
    if sign_flips or moshier_gaps:
        print("\n  VERDICT: Moshier alone is INSUFFICIENT if any of the above are")
        print("  non-zero for bodies your readings use. Chiron gaps confirm you")
        print("  need a Swiss/asteroid source (or a licensed swisseph) for those.")

    if args.fixed_stars:
        run_fixed_stars(args)
    swe.close()


# --------------------------------------------------------------------------- #
# Fixed stars (Regulus, Sirius, Algol, ...) — swisseph authority vs Skyfield.
# Fixed stars need NO asteroid/SPK data: catalog astrometry + precession only.
# --------------------------------------------------------------------------- #

def _unpack_fixstar(ret):
    """pyswisseph versions return the fixstar result in different orders/shapes
    (e.g. (xx, stnam, retflag) or (stnam, xx)). Locate the 6-float coordinate
    sequence and the star-name string defensively."""
    xx = None
    name = None
    for item in ret:
        if (isinstance(item, (list, tuple)) and len(item) >= 6
                and all(isinstance(v, (int, float)) for v in item[:6])):
            xx = item
        elif isinstance(item, str):
            name = item
    return xx, name


def compute_fixstar_swiss(jd_ut, swe_name):
    """Authority longitude for one fixed star from swisseph (apparent, of date)."""
    try:
        ret = swe.fixstar_ut(swe_name, jd_ut, swe.FLG_SWIEPH)
    except swe.Error:
        return None, None
    return _unpack_fixstar(ret)


def run_fixed_stars(args):
    """Emit a fixed-star oracle (swisseph authority) and, when requested and
    Skyfield is installed, a permissive Skyfield parity column."""
    try:
        import fixed_stars as fs
    except ImportError:
        print("[fixstar] fixed_stars.py not importable; skipping", file=sys.stderr)
        return

    step = max(1, args.fixstar_step_years)
    years = list(range(args.start, args.end + 1, step))
    instants = [(y, swe.julday(y, 1, 1, 0.0)) for y in years]

    engine = None
    if args.fixstar_candidate:
        try:
            engine = fs.SkyfieldFixedStarEngine(ephemeris_path=args.ephemeris_bsp)
        except Exception as exc:  # skyfield missing / ephemeris download failure
            print(f"[fixstar] Skyfield candidate disabled: {exc}", file=sys.stderr)

    records, rows = [], []
    max_arcsec = sum_arcsec = 0.0
    n = flips = missing = 0

    for (year, jd) in instants:
        for star in fs.NAMED_STARS:
            xx, _name = compute_fixstar_swiss(jd, star.swe_name)
            if xx is None:
                missing += 1
                continue
            swiss_lon = xx[0] % 360.0
            rec = {
                "year": year, "jd_ut": jd, "star": star.common_name,
                "swe_name": star.swe_name, "hip": star.hip,
                "traditions": list(star.traditions),
                "swiss_lon": swiss_lon, "swiss_pos": sign_and_degree(swiss_lon),
            }
            if engine is not None:
                try:
                    cand = engine.ecliptic_longitude(jd, star) % 360.0
                    arcsec = deg_to_arcsec(angular_sep_deg(swiss_lon, cand))
                    flip = zodiac_sign(swiss_lon) != zodiac_sign(cand)
                    rec.update({"candidate_lon": cand,
                                "candidate_pos": sign_and_degree(cand),
                                "delta_arcsec": arcsec, "sign_flip": flip})
                    max_arcsec = max(max_arcsec, arcsec)
                    sum_arcsec += arcsec
                    n += 1
                    flips += int(flip)
                    rows.append({
                        "year": year, "star": star.common_name, "hip": star.hip,
                        "swiss_lon": f"{swiss_lon:.6f}",
                        "candidate_lon": f"{cand:.6f}",
                        "delta_arcsec": f"{arcsec:.4f}",
                        "sign_flip": int(flip),
                        "swiss_pos": rec["swiss_pos"],
                        "candidate_pos": rec["candidate_pos"],
                    })
                except Exception as exc:
                    rec["candidate_error"] = str(exc)
            records.append(rec)

    os.makedirs(args.out, exist_ok=True)
    stars_path = os.path.join(args.out, "fixstars.json")
    with open(stars_path, "w", encoding="utf-8") as fh:
        json.dump({
            "meta": {
                "source_authority": "swisseph swe_fixstar_ut (FLG_SWIEPH)",
                "candidate": "Skyfield Star (MIT), ecliptic-of-date" if engine else None,
                "star_count": len(fs.NAMED_STARS),
                "year_range": [years[0], years[-1]] if years else [],
                "step_years": step,
                "note": "Longitudes are facts; safe to commit. Fixed stars need "
                        "NO asteroid/SPK data — catalog + precession only.",
            },
            "records": records,
        }, fh, indent=2)

    if rows:
        deltas_path = os.path.join(args.out, "fixstar_deltas.csv")
        with open(deltas_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print("\n=== Fixed-star oracle ===")
    print(f"  stars x instants     : {len(fs.NAMED_STARS)} x {len(instants)}")
    print(f"  swisseph misses      : {missing}  (name not matched in sefstars.txt)")
    if engine is not None and n:
        print(f"  Skyfield comparisons : {n}")
        print(f"  max longitude error  : {max_arcsec:9.3f} arcsec "
              f"({max_arcsec / 60.0:.3f} arcmin)")
        print(f"  mean longitude error : {sum_arcsec / n:9.3f} arcsec")
        print(f"  SIGN FLIPS           : {flips}  <-- interpretation-breaking")
    elif engine is None:
        print("  (run with --fixstar-candidate to add the Skyfield parity column)")
    print(f"  wrote {stars_path}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Swiss Ephemeris oracle generator "
                                            "(Moshier parity harness).")
    p.add_argument("--start", type=int, default=1950, help="start year (UT)")
    p.add_argument("--end", type=int, default=2100, help="end year (UT)")
    p.add_argument("--step-days", type=float, default=7.0, help="grid step (days)")
    p.add_argument("--ephe-path", default=os.environ.get("SE_EPHE_PATH", ""),
                   help="path to .se1 data files (needed for Chiron + best precision)")
    p.add_argument("--authority", choices=["swieph", "jpleph"], default="swieph",
                   help="swieph = swisseph's compressed DE431 (default); "
                        "jpleph = read a real JPL kernel (use with --jpl-file de440.bsp) "
                        "to align the authority onto the SAME ephemeris as the Skyfield "
                        "candidate, isolating convention differences from DE-vintage ones")
    p.add_argument("--jpl-file", default="",
                   help="JPL kernel filename in --ephe-path (e.g. de440.bsp); "
                        "only used when --authority jpleph")
    p.add_argument("--out", default="./fixtures", help="output directory")
    p.add_argument("--boundaries", action="store_true",
                   help="also emit sign-ingress boundary instants (slow, valuable)")
    p.add_argument("--fixed-stars", action="store_true",
                   help="also emit a fixed-star oracle (Regulus, Sirius, Algol, ...)")
    p.add_argument("--fixstar-candidate", action="store_true",
                   help="add a Skyfield (MIT) parity column for the fixed stars")
    p.add_argument("--fixstar-step-years", type=int, default=5,
                   help="sample fixed stars every N years (precession is slow)")
    p.add_argument("--ephemeris-bsp", default="de421.bsp",
                   help="JPL .bsp ephemeris for Skyfield fixed stars (auto-downloaded)")
    return p.parse_args(argv)


if __name__ == "__main__":
    run(parse_args())
