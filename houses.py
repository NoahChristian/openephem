#!/usr/bin/env python3
"""
houses.py — house systems + chart angles (Asc/MC/Vertex/East Point).  [SHIP]

Roadmap #2. Pure trigonometry (no ephemeris) — house math is standard positional
astronomy and not copyrightable. Inputs are ARMC (right ascension of the MC =
local apparent sidereal time in degrees), the obliquity of date, and geographic
latitude. A Skyfield helper (`angles_and_cusps_from_jd`) derives ARMC + obliquity
from a JD so this validates against swisseph's swe_houses in run_parity.py.

Implemented + reliable (closed form):
    * Angles: MC, Ascendant, Vertex, East Point (equatorial ascendant)
    * Whole Sign, Equal (from Asc), Porphyry
Implemented, FIRST PASS (validate via run_parity):
    * Placidus  — semi-arc method by bounded bisection between the anchors
Deferred (raise NotImplementedError; run_parity skips with a note):
    * Koch, Regiomontanus, Campanus — need their own arc formulas; queued so we
      don't ship unvalidated trig for them.

All longitudes are tropical, ecliptic of date, degrees in [0, 360).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

_D2R = math.pi / 180.0
_R2D = 180.0 / math.pi

CLOSED_FORM = {"WholeSign", "Equal", "Porphyry"}
ITERATIVE = {"Placidus"}
DEFERRED = {"Koch", "Regiomontanus", "Campanus"}
SUPPORTED = CLOSED_FORM | ITERATIVE


# --------------------------------------------------------------------------- #
# Spherical helpers (ecliptic point = latitude 0)
# --------------------------------------------------------------------------- #

def _ra_of(lon_deg: float, eps_deg: float) -> float:
    """Right ascension (deg) of the ecliptic point at longitude lon (lat 0)."""
    lon, eps = lon_deg * _D2R, eps_deg * _D2R
    return math.degrees(math.atan2(math.sin(lon) * math.cos(eps), math.cos(lon))) % 360.0


def _decl_of(lon_deg: float, eps_deg: float) -> float:
    """Declination (deg) of the ecliptic point at longitude lon (lat 0)."""
    lon, eps = lon_deg * _D2R, eps_deg * _D2R
    return math.degrees(math.asin(math.sin(eps) * math.sin(lon)))


def _norm180(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0


# --------------------------------------------------------------------------- #
# Chart angles
# --------------------------------------------------------------------------- #

def mc_longitude(armc_deg: float, eps_deg: float) -> float:
    a, e = armc_deg * _D2R, eps_deg * _D2R
    return math.degrees(math.atan2(math.sin(a), math.cos(a) * math.cos(e))) % 360.0


def ascendant(armc_deg: float, eps_deg: float, lat_deg: float) -> float:
    a, e, phi = armc_deg * _D2R, eps_deg * _D2R, lat_deg * _D2R
    asc = math.degrees(math.atan2(
        math.cos(a),
        -(math.sin(a) * math.cos(e) + math.tan(phi) * math.sin(e)))) % 360.0
    # Ascendant must lie in the semicircle zodiacally following the MC.
    mc = mc_longitude(armc_deg, eps_deg)
    if not (0.0 < (asc - mc) % 360.0 < 180.0):
        asc = (asc + 180.0) % 360.0
    return asc


def east_point(armc_deg: float, eps_deg: float) -> float:
    """Equatorial ascendant = Ascendant computed at latitude 0."""
    return ascendant(armc_deg, eps_deg, 0.0)


def vertex(armc_deg: float, eps_deg: float, lat_deg: float) -> float:
    """Vertex: the Ascendant of the co-latitude, taken on the western side."""
    anti = ascendant((armc_deg + 180.0) % 360.0, eps_deg, 90.0 - abs(lat_deg))
    # Anti-vertex is the eastern counterpart; vertex is opposite.
    return (anti + 180.0) % 360.0


# --------------------------------------------------------------------------- #
# House systems
# --------------------------------------------------------------------------- #

def _whole_sign(asc: float) -> list[float]:
    base = math.floor(asc / 30.0) * 30.0
    return [(base + 30.0 * i) % 360.0 for i in range(12)]


def _equal(asc: float) -> list[float]:
    return [(asc + 30.0 * i) % 360.0 for i in range(12)]


def _porphyry(asc: float, mc: float) -> list[float]:
    """Trisect the ecliptic arcs between the four angles."""
    ic = (mc + 180.0) % 360.0
    desc = (asc + 180.0) % 360.0
    q1 = (asc - ic) % 360.0     # IC -> Asc  (houses 2,3 fill this backwards)
    q2 = (mc - asc) % 360.0     # Asc -> MC? sign handling below
    # Build via the four quadrants Asc->IC->Desc->MC->Asc, trisecting each.
    cusps = [0.0] * 12
    cusps[0] = asc            # 1
    cusps[3] = ic             # 4
    cusps[6] = desc           # 7
    cusps[9] = mc             # 10
    arc_1_4 = (ic - asc) % 360.0
    arc_4_7 = (desc - ic) % 360.0
    arc_7_10 = (mc - desc) % 360.0
    arc_10_1 = (asc - mc) % 360.0
    cusps[1] = (asc + arc_1_4 / 3.0) % 360.0
    cusps[2] = (asc + 2.0 * arc_1_4 / 3.0) % 360.0
    cusps[4] = (ic + arc_4_7 / 3.0) % 360.0
    cusps[5] = (ic + 2.0 * arc_4_7 / 3.0) % 360.0
    cusps[7] = (desc + arc_7_10 / 3.0) % 360.0
    cusps[8] = (desc + 2.0 * arc_7_10 / 3.0) % 360.0
    cusps[10] = (mc + arc_10_1 / 3.0) % 360.0
    cusps[11] = (mc + 2.0 * arc_10_1 / 3.0) % 360.0
    return cusps


def _placidus_intermediate(armc: float, eps: float, phi: float,
                           frac: float, nocturnal: bool,
                           lo: float, hi: float) -> float:
    """Solve for an intermediate Placidus cusp longitude by bisection on the
    ecliptic arc (lo, hi). Condition: the point's meridian distance equals
    `frac` of its semi-diurnal (or semi-nocturnal) arc."""
    def g(lon: float) -> float:
        dec = _decl_of(lon, eps)
        t = math.tan(phi * _D2R) * math.tan(dec * _D2R)
        if abs(t) >= 1.0:
            return math.nan  # circumpolar: undefined here
        ad = math.degrees(math.asin(t))              # ascensional difference
        semi = (90.0 - ad) if nocturnal else (90.0 + ad)
        ra = _ra_of(lon, eps)
        # Meridian distance measured toward the cusp's own meridian: for diurnal
        # cusps (11,12) east of the upper meridian md = ra-ARMC; for nocturnal
        # cusps (2,3) the points sit west of the lower meridian, so md = ref-ra.
        ref = (armc + 180.0) if nocturnal else armc
        md = _norm180((ref - ra) if nocturnal else (ra - ref))
        return md - frac * semi

    # Expand the bracket over the (lo,hi) arc, then bisect on a sign change.
    n = 64
    span = (hi - lo) % 360.0
    prev_x = lo
    prev = g(lo)
    for i in range(1, n + 1):
        x = (lo + span * i / n) % 360.0
        val = g(x)
        if not math.isnan(prev) and not math.isnan(val) and prev == 0.0:
            return prev_x % 360.0
        if not math.isnan(prev) and not math.isnan(val) and (prev < 0.0) != (val < 0.0):
            a, b, fa = prev_x, x, prev
            for _ in range(60):
                m = a + ((b - a) % 360.0) / 2.0
                fm = g(m % 360.0)
                if math.isnan(fm):
                    break
                if (fa < 0.0) != (fm < 0.0):
                    b = m
                else:
                    a, fa = m, fm
            return (a % 360.0)
        prev_x, prev = x, val
    return math.nan  # no bracket found (e.g. high latitude)


def _placidus(armc: float, eps: float, phi: float,
              asc: float, mc: float) -> list[float]:
    if abs(phi) >= 66.0:
        raise ValueError("Placidus is undefined within the polar circle (|lat|>=66)")
    ic = (mc + 180.0) % 360.0
    desc = (asc + 180.0) % 360.0
    cusps = [0.0] * 12
    cusps[0], cusps[3], cusps[6], cusps[9] = asc, ic, desc, mc
    # 11,12 between MC and Asc (upper, diurnal); 2,3 between Asc and IC (nocturnal)
    cusps[10] = _placidus_intermediate(armc, eps, phi, 1.0 / 3.0, False, mc, asc)   # 11
    cusps[11] = _placidus_intermediate(armc, eps, phi, 2.0 / 3.0, False, mc, asc)   # 12
    cusps[1] = _placidus_intermediate(armc, eps, phi, 2.0 / 3.0, True, asc, ic)     # 2
    cusps[2] = _placidus_intermediate(armc, eps, phi, 1.0 / 3.0, True, asc, ic)     # 3
    # opposite cusps
    cusps[4] = (cusps[10] + 180.0) % 360.0
    cusps[5] = (cusps[11] + 180.0) % 360.0
    cusps[7] = (cusps[1] + 180.0) % 360.0
    cusps[8] = (cusps[2] + 180.0) % 360.0
    return cusps


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

@dataclass
class Houses:
    system: str
    asc: float
    mc: float
    vertex: float
    east_point: float
    cusps: list[float]  # 1..12


def compute(armc_deg: float, eps_deg: float, lat_deg: float,
            system: str = "Placidus") -> Houses:
    if system in DEFERRED:
        raise NotImplementedError(
            f"{system} house system not implemented yet (needs its own arc "
            "formula); run_parity skips it rather than ship unvalidated trig")
    if system not in SUPPORTED:
        raise KeyError(f"unknown house system: {system}")

    asc = ascendant(armc_deg, eps_deg, lat_deg)
    mc = mc_longitude(armc_deg, eps_deg)
    if system == "WholeSign":
        cusps = _whole_sign(asc)
    elif system == "Equal":
        cusps = _equal(asc)
    elif system == "Porphyry":
        cusps = _porphyry(asc, mc)
    elif system == "Placidus":
        cusps = _placidus(armc_deg, eps_deg, lat_deg, asc, mc)
    return Houses(system=system, asc=asc, mc=mc,
                  vertex=vertex(armc_deg, eps_deg, lat_deg),
                  east_point=east_point(armc_deg, eps_deg), cusps=cusps)


def mean_obliquity(jd_tt: float) -> float:
    """Mean obliquity of the ecliptic (deg), IAU. Sufficient for house cusps
    (nutation-in-obliquity is <9.2\" — below house-placement resolution)."""
    T = (jd_tt - 2451545.0) / 36525.0
    sec = (84381.406 - 46.836769 * T - 0.0001831 * T**2
           + 0.00200340 * T**3 - 5.76e-7 * T**4 - 4.34e-8 * T**5)
    return sec / 3600.0


def gmst_deg(jd_ut: float) -> float:
    """Greenwich Mean Sidereal Time in degrees (IAU 1982) — analytic, no ephemeris."""
    T = (jd_ut - 2451545.0) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd_ut - 2451545.0)
         + 0.000387933 * T * T - T * T * T / 38710000.0)
    return g % 360.0


def houses_from_jd(jd_ut: float, lat_deg: float, lon_deg: float,
                   system: str = "Placidus") -> Houses:
    """Houses from JD(UT) + geographic lat/lon — fully standalone (no Skyfield).
    ARMC uses mean sidereal time and obliquity is mean-of-date; both omit nutation
    (equation-of-equinoxes + nutation-in-obliquity < ~20\", below cusp resolution).
    run_parity.py quantifies the residual against swisseph's apparent values."""
    armc = (gmst_deg(jd_ut) + lon_deg) % 360.0
    eps = mean_obliquity(jd_ut)   # jd_ut ~ jd_tt for obliquity (dT effect < 0.01")
    return compute(armc, eps, lat_deg, system)


if __name__ == "__main__":
    # ARMC=0, eps=23.4367, lat=51.5 (London-ish) — smoke check of the angles.
    h = compute(0.0, 23.4367, 51.5, "Placidus")
    print("Asc", round(h.asc, 3), "MC", round(h.mc, 3),
          "Vtx", round(h.vertex, 3), "EP", round(h.east_point, 3))
    print("cusps", [round(c, 2) for c in h.cusps])
