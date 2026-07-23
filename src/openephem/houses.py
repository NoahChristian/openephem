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
QUADRANT = {"Placidus", "Regiomontanus", "Campanus", "Koch"}
DEFERRED = set()
SUPPORTED = CLOSED_FORM | QUADRANT


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
    """Vertex: the Ascendant computed for the co-latitude on the opposite meridian
    IS the vertex directly (parity vs swisseph confirmed no extra 180° flip)."""
    return ascendant((armc_deg + 180.0) % 360.0, eps_deg, 90.0 - abs(lat_deg))


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
# Regiomontanus / Koch / Campanus (validated against swisseph to < 1e-6 deg)
# --------------------------------------------------------------------------- #

def _in_arc(c: float, lo: float, hi: float) -> float:
    c %= 360.0
    if not (0.0 <= (c - lo) % 360.0 <= (hi - lo) % 360.0):
        c = (c + 180.0) % 360.0
    return c


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _regiomontanus(armc, eps, phi):
    """Cusps 11,12,2,3: equal 30-deg EQUATORIAL arcs from the MC, projected
    through the horizon N-S points onto the ecliptic."""
    er = math.radians(eps)
    def cusp(H):
        ar = math.radians(armc + H)
        R = math.atan2(math.sin(math.radians(H)) * math.tan(math.radians(phi)), math.cos(ar))
        return math.degrees(math.atan2(math.cos(R) * math.sin(ar),
                                       math.cos(R + er) * math.cos(ar))) % 360.0
    return [cusp(30), cusp(60), cusp(120), cusp(150)]


def _koch(armc, eps, phi, mc):
    """Cusps by trisecting the MC->Asc oblique-ascension arc; the step k absorbs
    the MC's ascensional difference AD_MC."""
    ad = math.degrees(math.asin(max(-1.0, min(1.0,
        math.tan(math.radians(phi)) * math.tan(math.radians(_decl_of(mc, eps)))))))
    k = (90.0 + ad) / 3.0
    return [ascendant(armc - 2 * k, eps, phi), ascendant(armc - k, eps, phi),
            ascendant(armc + k, eps, phi), ascendant(armc + 2 * k, eps, phi)]


def _campanus(armc, eps, phi):
    """Cusps: equal 30-deg PRIME-VERTICAL arcs from the east point, projected
    through the horizon N-S axis onto the ecliptic (vector intersection)."""
    a, e, p = math.radians(armc), math.radians(eps), math.radians(phi)
    east = (-math.sin(a), math.cos(a), 0.0)
    up = (math.cos(p) * math.cos(a), math.cos(p) * math.sin(a), math.sin(p))
    N = (-math.sin(p) * math.cos(a), -math.sin(p) * math.sin(a), math.cos(p))
    eclpole = (0.0, -math.sin(e), math.cos(e))
    def cusp(D):
        cd, sd = math.cos(math.radians(D)), math.sin(math.radians(D))
        P = (cd * east[0] + sd * up[0], cd * east[1] + sd * up[1], cd * east[2] + sd * up[2])
        v = _cross(_cross(N, P), eclpole)
        vy = v[1] * math.cos(e) + v[2] * math.sin(e)
        return math.degrees(math.atan2(vy, v[0])) % 360.0
    # cusp 11 = 60deg up, 12 = 30 up, 2 = 30 down, 3 = 60 down (from the east point)
    return [cusp(60), cusp(30), cusp(-30), cusp(-60)]


def _assemble_quadrant(inter, asc, mc):
    """Normalize the 4 raw intermediate cusps [11,12,2,3] into their arcs and
    build the full 12-cusp list (opposite cusps are 180 deg away)."""
    ic = (mc + 180.0) % 360.0
    c11 = _in_arc(inter[0], mc, asc)
    c12 = _in_arc(inter[1], mc, asc)
    c2 = _in_arc(inter[2], asc, ic)
    c3 = _in_arc(inter[3], asc, ic)
    return [asc, c2, c3, ic, (c11 + 180) % 360, (c12 + 180) % 360,
            (asc + 180) % 360, (c2 + 180) % 360, (c3 + 180) % 360, mc, c11, c12]


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
    elif system == "Regiomontanus":
        cusps = _assemble_quadrant(_regiomontanus(armc_deg, eps_deg, lat_deg), asc, mc)
    elif system == "Koch":
        cusps = _assemble_quadrant(_koch(armc_deg, eps_deg, lat_deg, mc), asc, mc)
    elif system == "Campanus":
        cusps = _assemble_quadrant(_campanus(armc_deg, eps_deg, lat_deg), asc, mc)
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


def nutation(jd: float) -> tuple[float, float]:
    """Nutation in longitude (dpsi) and obliquity (deps), in degrees. Truncated
    IAU-1980 series (largest terms) — ~1" accuracy, enough for house cusps."""
    T = (jd - 2451545.0) / 36525.0
    d2r = math.pi / 180.0
    om = 125.04452 - 1934.136261 * T           # Moon ascending node
    ls = 280.4665 + 36000.7698 * T             # Sun mean longitude
    lm = 218.3165 + 481267.8813 * T            # Moon mean longitude
    dpsi = (-17.20 * math.sin(d2r * om) - 1.32 * math.sin(d2r * 2 * ls)
            - 0.23 * math.sin(d2r * 2 * lm) + 0.21 * math.sin(d2r * 2 * om)) / 3600.0
    deps = (9.20 * math.cos(d2r * om) + 0.57 * math.cos(d2r * 2 * ls)
            + 0.10 * math.cos(d2r * 2 * lm) - 0.09 * math.cos(d2r * 2 * om)) / 3600.0
    return dpsi, deps


# Long-term sidereal-time correction. IAU-1982 GMST is only accurate over a few
# centuries; swisseph uses long-term precession (Vondrak), so GMST diverges up to
# ~326" by year 0. This deg-5 polynomial (fit offline vs swisseph over yr 1-2600;
# coefficients are facts) matches swisseph's sidereal time to ~arcsec across
# 0-2500, and is ~0 in the modern era. Calibrated for ~0-2600; outside that it
# extrapolates (production charts are 1900-2100, where it is negligible).
_ST_CORR = (0.0555751, -1.00943, 0.075145, 0.069184, 0.0139427, 0.000440869)  # arcsec T^0..5


def _st_longterm_correction_deg(jd_ut: float) -> float:
    T = (jd_ut - 2451545.0) / 36525.0
    return sum(_ST_CORR[k] * T**k for k in range(6)) / 3600.0


def houses_from_jd(jd_ut: float, lat_deg: float, lon_deg: float,
                   system: str = "Placidus") -> Houses:
    """Houses from JD(UT) + geographic lat/lon — fully standalone (no Skyfield).
    Uses APPARENT sidereal time (GMST + equation of equinoxes + long-term
    correction) and TRUE obliquity (mean + nutation), matching swe_houses across
    0-2500."""
    dpsi, deps = nutation(jd_ut)               # dT effect on nutation args < 0.01"
    eps_mean = mean_obliquity(jd_ut)
    eps_true = eps_mean + deps
    eq_equinox = dpsi * math.cos(math.radians(eps_mean))   # GAST - GMST
    armc = (gmst_deg(jd_ut) + eq_equinox
            + _st_longterm_correction_deg(jd_ut) + lon_deg) % 360.0
    return compute(armc, eps_true, lat_deg, system)


if __name__ == "__main__":
    # ARMC=0, eps=23.4367, lat=51.5 (London-ish) — smoke check of the angles.
    h = compute(0.0, 23.4367, 51.5, "Placidus")
    print("Asc", round(h.asc, 3), "MC", round(h.mc, 3),
          "Vtx", round(h.vertex, 3), "EP", round(h.east_point, 3))
    print("cusps", [round(c, 2) for c in h.cusps])
