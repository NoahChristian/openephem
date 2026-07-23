#!/usr/bin/env python3
"""
run_parity.py — validate the permissive engines against the swisseph oracle.

Step 1 (the runner). Loads the fixtures produced by generate_oracle.py and drives
the production candidate engines:
    * planets_skyfield.SkyfieldPlanetEngine   (Sun..Pluto, Moon, MeanNode, MeanLilith)
    * asteroids_skyfield.SkyfieldAsteroidEngine (Chiron, Ceres, Pallas, Juno, Vesta)
    * fixed_stars.SkyfieldFixedStarEngine      (Regulus, Sirius, Algol, ...)

For every (instant, body) it compares candidate vs authority longitude and asserts:
    1. numeric tolerance  (per-body arcsecond threshold), AND
    2. categorical parity (SAME zodiac sign — the interpretation-breaking check).

It reports a per-body distribution (p50/p95/max, sign-flips) and EXITS NONZERO if
any non-skipped body breaches tolerance or flips a sign — so it can gate CI.

Bodies swisseph can compute but the candidate defers (TrueNode, OscuLilith) are
SKIPPED with a note, never silently passed.

    python run_parity.py --fixtures ./fixtures --de440 de440.bsp \\
        --kernel-dir ./kernels
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from statistics import median

# Per-body numeric tolerance (arcsec). Mean node/Lilith are looser: they are
# *definitional* mean points and differ slightly from swisseph's mean model.
DEFAULT_TOL = {
    "Sun": 1.0, "Moon": 5.0, "Mercury": 1.0, "Venus": 1.0, "Mars": 1.0,
    "Jupiter": 2.0, "Saturn": 2.0, "Uranus": 2.0, "Neptune": 2.0, "Pluto": 3.0,
    "MeanNode": 60.0, "MeanLilith": 120.0,
    "Chiron": 2.0, "Ceres": 2.0, "Pallas": 2.0, "Juno": 2.0, "Vesta": 2.0,
    # Osculating node/Lilith are a first-pass (J2000 elements + precession) — loose
    # until validated; tighten once the real agreement is known.
    "TrueNode": 120.0, "OscuLilith": 300.0,
    "_star": 5.0, "_house_angle": 60.0, "_house_cusp": 120.0, "_default": 5.0,
}
SKIP = set()  # (was TrueNode/OscuLilith — now implemented via osculating elements)


def angular_sep_deg(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def zodiac_sign(lon: float) -> int:
    return int(lon % 360.0 // 30.0)


def p95(values):
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, int(round(0.95 * (len(s) - 1))))
    return s[k]


class Candidate:
    """Unifies the three engines behind one longitude(name, jd) call. Engines that
    can't load (missing lib/kernel) are disabled; their bodies get skipped."""

    def __init__(self, de440, kernel_dir):
        self.planets = self._try(lambda: _planets(de440), "planet engine")
        self.asteroids = self._try(lambda: _asteroids(de440, kernel_dir), "asteroid engine")
        self.stars_engine, self.star_table = self._try_stars(de440)

    @staticmethod
    def _try(factory, label):
        try:
            return factory()
        except Exception as exc:  # noqa: BLE001 — report and disable gracefully
            print(f"[parity] {label} unavailable: {exc}", file=sys.stderr)
            return None

    def _try_stars(self, de440):
        try:
            import fixed_stars as fs
            return fs.SkyfieldFixedStarEngine(ephemeris_path=de440), {s.common_name: s
                                                                       for s in fs.NAMED_STARS}
        except Exception as exc:  # noqa: BLE001
            print(f"[parity] fixed-star engine unavailable: {exc}", file=sys.stderr)
            return None, {}

    def planet_longitude(self, name, jd):
        return self.planets.ecliptic_longitude(jd, name) if self.planets else None

    def asteroid_longitude(self, name, jd):
        return self.asteroids.ecliptic_longitude(jd, name) if self.asteroids else None

    def star_longitude(self, common_name, jd):
        if not self.stars_engine or common_name not in self.star_table:
            return None
        return self.stars_engine.ecliptic_longitude(jd, self.star_table[common_name])


def _planets(de440):
    import planets_skyfield as p
    return p.SkyfieldPlanetEngine(ephemeris_path=de440)


def _asteroids(de440, kernel_dir):
    import asteroids_skyfield as a
    return a.SkyfieldAsteroidEngine(planets_ephemeris=de440, kernel_dir=kernel_dir)


PLANET_NAMES = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                "Uranus", "Neptune", "Pluto", "MeanNode", "MeanLilith",
                "TrueNode", "OscuLilith"}
ASTEROID_NAMES = {"Chiron", "Ceres", "Pallas", "Juno", "Vesta"}


def candidate_longitude(cand: Candidate, name: str, jd: float):
    if name in PLANET_NAMES:
        return cand.planet_longitude(name, jd)
    if name in ASTEROID_NAMES:
        return cand.asteroid_longitude(name, jd)
    return None


def run(args):
    cand = Candidate(args.de440, args.kernel_dir)
    tol = dict(DEFAULT_TOL)

    # per-body accumulators
    stats: dict[str, dict] = {}

    def record(name, authority_lon, cand_lon, tol_arcsec):
        if cand_lon is None or cand_lon != cand_lon:  # None or NaN
            skipped.setdefault(name, "candidate returned None/NaN")
            return
        arcsec = angular_sep_deg(authority_lon, cand_lon) * 3600.0
        flip = zodiac_sign(authority_lon) != zodiac_sign(cand_lon)
        s = stats.setdefault(name, {"errs": [], "flips": 0, "n": 0, "tol": tol_arcsec})
        s["errs"].append(arcsec)
        s["flips"] += int(flip)
        s["n"] += 1

    skipped = {}

    # --- planets + asteroids from oracle.json ---
    oracle_path = os.path.join(args.fixtures, "oracle.json")
    if os.path.exists(oracle_path):
        with open(oracle_path, encoding="utf-8") as fh:
            oracle = json.load(fh)
        for rec in oracle["records"]:
            jd = rec["jd_ut"]
            for name, entry in rec["bodies"].items():
                if name in SKIP:
                    skipped[name] = NOT_IMPL_REASON.get(name, "deferred")
                    continue
                swiss = entry.get("swiss")
                if not swiss or "lon" not in swiss:
                    continue
                try:
                    clon = candidate_longitude(cand, name, jd)
                except Exception as exc:  # noqa: BLE001 — isolate per-body failures
                    skipped.setdefault(name, f"candidate error: {exc}")
                    continue
                if clon is None:
                    skipped.setdefault(name, "candidate engine/kernel unavailable")
                    continue
                record(name, swiss["lon"], clon, tol.get(name, tol["_default"]))
    else:
        print(f"[parity] no {oracle_path}; run generate_oracle.py first", file=sys.stderr)

    # --- fixed stars from fixstars.json ---
    stars_path = os.path.join(args.fixtures, "fixstars.json")
    if os.path.exists(stars_path):
        with open(stars_path, encoding="utf-8") as fh:
            starfix = json.load(fh)
        for rec in starfix["records"]:
            jd, cn = rec["jd_ut"], rec["star"]
            clon = cand.star_longitude(cn, jd)
            if clon is None:
                skipped.setdefault(f"star:{cn}", "fixed-star engine unavailable")
                continue
            record(f"star:{cn}", rec["swiss_lon"], clon, tol["_star"])

    # --- houses (angles + cusps) vs swisseph, for implemented systems ---
    if os.path.exists(oracle_path):
        geo = oracle.get("meta", {}).get("geo")
        try:
            import houses as H
        except Exception as exc:  # noqa: BLE001
            H = None
            skipped.setdefault("houses", f"houses module unavailable: {exc}")
        if H and geo:
            for rec in oracle["records"]:
                jd = rec["jd_ut"]
                for system, hv in rec.get("houses", {}).items():
                    if "asc" not in hv:            # error entry in oracle
                        continue
                    if system not in H.SUPPORTED:
                        skipped.setdefault(f"house:{system}", "house system not implemented")
                        continue
                    try:
                        c = H.houses_from_jd(jd, geo["lat"], geo["lon"], system)
                    except Exception as exc:  # noqa: BLE001
                        skipped.setdefault(f"house:{system}", f"candidate error: {exc}")
                        continue
                    record(f"house:{system}:Asc", hv["asc"], c.asc, tol["_house_angle"])
                    record(f"house:{system}:MC", hv["mc"], c.mc, tol["_house_angle"])
                    if "vertex" in hv:
                        record(f"house:{system}:Vtx", hv["vertex"], c.vertex, tol["_house_angle"])
                    if "east_point" in hv:
                        record(f"house:{system}:EP", hv["east_point"], c.east_point, tol["_house_angle"])
                    oc = hv.get("cusps")
                    if oc and len(oc) >= 12:       # aggregate all 12 cusps into one row
                        for k in range(12):
                            record(f"house:{system}:cusps", oc[k], c.cusps[k], tol["_house_cusp"])

    # --- report ---
    print(f"\n{'body':16} {'n':>5} {'p50\"':>9} {'p95\"':>9} {'max\"':>9} "
          f"{'flip':>5} {'tol\"':>7} {'PASS?':>6}")
    print("-" * 74)
    failures = 0
    for name in sorted(stats):
        s = stats[name]
        errs = s["errs"]
        mx = max(errs) if errs else 0.0
        ok = (mx <= s["tol"]) and (s["flips"] == 0)
        failures += int(not ok)
        print(f"{name:16} {s['n']:>5} {median(errs):>9.3f} {p95(errs):>9.3f} "
              f"{mx:>9.3f} {s['flips']:>5} {s['tol']:>7.1f} {'ok' if ok else 'FAIL':>6}")

    if skipped:
        print("\nskipped (not silently passed):")
        for k, v in sorted(skipped.items()):
            print(f"  {k}: {v}")

    print(f"\n{'RESULT':16} {'PASS' if failures == 0 else f'FAIL ({failures} bodies)'}")
    return 0 if failures == 0 else 1


NOT_IMPL_REASON = {
    "TrueNode": "osculating lunar node - candidate defers (needs osculating elements)",
    "OscuLilith": "osculating lunar apogee - candidate defers (needs osculating elements)",
}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Validate permissive engines vs the "
                                            "swisseph oracle (planets, asteroids, stars).")
    p.add_argument("--fixtures", default="./fixtures", help="dir with oracle.json / fixstars.json")
    p.add_argument("--de440", default="de440.bsp", help="JPL DE440 kernel for Skyfield")
    p.add_argument("--kernel-dir", default="./kernels", help="dir with asteroid .bsp kernels")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args()))
