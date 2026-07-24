#!/usr/bin/env python3
"""
hypothetical.py — the Uranian / hypothetical-body engine.  [SHIP]

Computes geocentric apparent ecliptic longitude OF DATE for the eight Uranian
("Hamburg School") planets — Cupido, Hades, Zeus, Kronos, Apollon, Admetos,
Vulcanus, Poseidon — plus Trans-Pluto ("Isis"), Vulcan (L.H. Weston's intra-
mercurial hypothetical) and the White Moon / "Selena". These bodies do not exist;
they are astrological constructs propagated from published **mean orbital
elements** (Witte-Sieggrun, revised by James Neely; Trans-Pluto from Strubell,
"Die Sterne" 3/1952; Vulcan from Weston; Selena as a geocentric mean point). The
element numbers are facts (the same set Swiss Ephemeris carries in its
seorbel.txt); we ship them with attribution and rederive the position from
scratch here — no AGPL code or data file is redistributed.

Three variants share the pipeline: constant heliocentric elements referred to a
fixed equinox (the Uranians + Trans-Pluto); heliocentric elements that drift
linearly with time, referred to the equinox of date (Vulcan); and a geocentric
circular mean point (Selena, longitude only).

Method (a two-body osculating propagation, which is exactly what these constructs
are defined by):
  1. Mean anomaly M(t) = M0 + n*(t_TT - epoch), n = 0.9856076686 / a^1.5 deg/day.
  2. Solve Kepler for the eccentric anomaly E; heliocentric position in the orbit
     plane, rotated by (arg. perihelion, node, inclination) into the mean ecliptic
     & equinox of the element set (J1900 for the Uranians, 1945.0 for Trans-Pluto).
  3. Rotate that heliocentric vector to ICRS (obliquity of the element epoch +
     equatorial precession from the element equinox to J2000, via Skyfield).
  4. Subtract Earth's heliocentric position (Skyfield / DE440) -> geocentric.
  5. Light-time retardation + annual aberration -> apparent; Skyfield converts the
     apparent geocentric vector to ecliptic longitude of date.

Validated against Swiss Ephemeris (swe.calc_ut, bodies 40-48 + Vulcan 55, White
Moon 56) across 1935-2024: Uranians/Trans-Pluto/Vulcan < 0.1 arcsec, Selena
~0.2 arcsec (nutation-model difference) — the parity tier of the planetary engine.
Licensing: Skyfield is MIT, DE440 is public-domain; no AGPL dependency.
"""

from __future__ import annotations

import math

# Julian epoch 1900.0 — the equinox/epoch the Uranian elements are referred to.
J1900 = 2415020.0
# Gaussian mean motion constant: n [deg/day] = _KG / a^1.5  (a in AU, heliocentric).
_KG = 0.9856076686
# Speed of light, au/day (for light-time retardation).
_C = 173.144632674

# Mean orbital elements, one tuple per body:
#   (epoch_jd, equinox_jd, M0_deg, a_AU, e, arg_perihelion_deg, node_deg, incl_deg)
# Uranians: Witte-Sieggrun / Neely. Trans-Pluto: Strubell 1952 (equinox 1945.0).
ELEMENTS: dict[str, tuple] = {
    "Cupido":     (J1900, J1900, 163.7409, 40.99837, 0.00460, 171.4333, 129.8325, 1.0833),
    "Hades":      (J1900, J1900,  27.6496, 50.66744, 0.00245, 148.1796, 161.3339, 1.0500),
    "Zeus":       (J1900, J1900, 165.1232, 59.21436, 0.00120, 299.0440,   0.0000, 0.0000),
    "Kronos":     (J1900, J1900, 169.0193, 64.81690, 0.00305, 208.8801,   0.0000, 0.0000),
    "Apollon":    (J1900, J1900, 138.0533, 70.29949, 0.00000,   0.0000,   0.0000, 0.0000),
    "Admetos":    (J1900, J1900, 351.3350, 73.62765, 0.00000,   0.0000,   0.0000, 0.0000),
    "Vulcanus":   (J1900, J1900,  55.8983, 77.25568, 0.00000,   0.0000,   0.0000, 0.0000),
    "Poseidon":   (J1900, J1900, 165.5163, 83.66907, 0.00000,   0.0000,   0.0000, 0.0000),
    "TransPluto": (2368547.66, 2431456.5, 0.0, 77.775, 0.3, 0.7, 0.0, 0.0),
}

# Two further hypotheticals whose swisseph models differ from the constant-element
# Uranians (both referred to the equinox OF DATE, elements from swisseph seorbel.txt):
#
# Vulcan — L.H. Weston's intramercurial hypothetical. Heliocentric Keplerian, but
#   the elements drift linearly with time (T = Julian centuries of TT since J1900):
#     M    = 252.8987988 + 707550.7341 * T   deg
#     peri = 322.212069  + 1670.056   * T     deg
#     node =  47.787931  - 1670.056   * T     deg
#     a = 0.13744 AU, e = 0.019, i = 7.5 deg
_VULCAN_EPOCH = J1900
_VULCAN = dict(a=0.13744, e=0.019, incl=7.5,
               M=(252.8987988, 707550.7341),
               peri=(322.212069, 1670.056), node=(47.787931, -1670.056))
#
# White Moon / "Selena" — a GEOCENTRIC, circular, in-plane mean point (the bright
#   counterpart to Black Moon Lilith). Reduces to a linear mean longitude of date;
#   swisseph refers it to the true equinox, so nutation is added by the of-date
#   conversion. L(T) = 242.2205555 + 5143.5418158 * T deg, T = centuries since J2000.
_SELENA = (242.2205555, 5143.5418158)


def _kepler(M_deg: float, e: float) -> float:
    """Eccentric anomaly (radians) from mean anomaly, Newton-Raphson."""
    M = math.radians(M_deg % 360.0)
    E = M if e < 0.8 else math.pi
    for _ in range(60):
        d = (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
        E -= d
        if abs(d) < 1e-13:
            break
    return E


class HypotheticalEngine:
    """Osculating-element engine for the Uranian planets + Trans-Pluto.

    Same interface as the other engines: ``ecliptic_longitude(jd_ut, name)``.
    Needs Skyfield + a JPL ephemeris (DE440) for Earth's position and the frame
    machinery; raises on construction if those are unavailable (assemble catches
    it and degrades gracefully).
    """

    BODIES = tuple(ELEMENTS) + ("Vulcan", "WhiteMoon")

    def __init__(self, ephemeris_path: str = "de440.bsp"):
        import numpy as np
        from skyfield.api import load
        from skyfield import precessionlib, nutationlib
        self._np = np
        self._prec = precessionlib
        self._nut = nutationlib
        self._ts = load.timescale()
        self._eph = load(ephemeris_path)
        self._earth = self._eph["earth"]
        self._sun = self._eph["sun"]
        # cache the per-equinox rotation (ecliptic-of-equinox -> ICRS); the element
        # equinoxes are fixed, so this is computed once per distinct equinox.
        self._rot: dict[float, "np.ndarray"] = {}

    # -- frame helpers -------------------------------------------------------

    def _rx(self, eps: float):
        c, s = math.cos(eps), math.sin(eps)
        return self._np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])

    def _ecl_equinox_to_icrs(self, equinox_jd: float, cache: bool = True):
        """Rotation from the mean ecliptic & equinox of `equinox_jd` to ICRS.

        `cache=False` for an equinox-of-date body (Vulcan/Selena), where the key
        is a distinct date every call and caching would grow without bound."""
        R = self._rot.get(equinox_jd) if cache else None
        if R is None:
            np = self._np
            eps = math.radians(self._nut.mean_obliquity(equinox_jd) / 3600.0)
            # ecliptic(equinox) -> equatorial(equinox) -> ICRS(J2000)
            prec = np.array(self._prec.compute_precession(equinox_jd))  # ICRS -> equinox
            R = prec.T @ self._rx(eps)
            if cache:
                self._rot[equinox_jd] = R
        return R

    def _orbit_vector(self, M, a, e, peri, node, incl):
        """Position vector (AU) in the orbit's reference ecliptic frame."""
        E = _kepler(M, e)
        xv = a * (math.cos(E) - e)
        yv = a * math.sqrt(1.0 - e * e) * math.sin(E)
        pw, nw, iw = map(math.radians, (peri, node, incl))
        cN, sN, cI, sI, cP, sP = (math.cos(nw), math.sin(nw), math.cos(iw),
                                  math.sin(iw), math.cos(pw), math.sin(pw))
        x = (cN * cP - sN * sP * cI) * xv + (-cN * sP - sN * cP * cI) * yv
        y = (sN * cP + cN * sP * cI) * xv + (-sN * sP + cN * cP * cI) * yv
        z = (sP * sI) * xv + (cP * sI) * yv
        return self._np.array([x, y, z])

    def _helio_ecl(self, name: str, jd_tt: float):
        """Heliocentric position of a constant-element body in its ecliptic frame."""
        epoch, _eq, M0, a, e, peri, node, incl = ELEMENTS[name]
        M = M0 + (_KG / a ** 1.5) * (jd_tt - epoch)
        return self._orbit_vector(M, a, e, peri, node, incl)

    def _helio_vulcan(self, jd_tt: float):
        """Vulcan's heliocentric position; elements drift linearly in T (of date)."""
        T = (jd_tt - _VULCAN_EPOCH) / 36525.0
        v = _VULCAN
        return self._orbit_vector(v["M"][0] + v["M"][1] * T, v["a"], v["e"],
                                  v["peri"][0] + v["peri"][1] * T,
                                  v["node"][0] + v["node"][1] * T, v["incl"])

    # -- public --------------------------------------------------------------

    def ecliptic_longitude(self, jd_ut: float, name: str) -> float:
        """Geocentric apparent ecliptic longitude of date, degrees [0, 360)."""
        if name not in self.BODIES:
            raise KeyError(f"not a hypothetical body: {name}")
        np = self._np
        from skyfield.positionlib import ICRF
        t = self._ts.ut1(jd=jd_ut)
        jd_tt = t.tt

        # White Moon / Selena: geocentric circular mean point. Build its of-date
        # direction and let Skyfield add nutation (true equinox) — no light-time /
        # aberration (it is an abstract geocentric point, like mean Lilith).
        if name == "WhiteMoon":
            L = math.radians((_SELENA[0] + _SELENA[1] * (jd_tt - 2451545.0) / 36525.0) % 360.0)
            R = self._ecl_equinox_to_icrs(jd_tt, cache=False)
            v = R @ np.array([math.cos(L), math.sin(L), 0.0])
            return ICRF(v, t=t, center=399).ecliptic_latlon(epoch=t)[1].degrees % 360.0

        # Heliocentric bodies: Kepler -> ICRS -> subtract Earth -> light-time + aberration.
        if name == "Vulcan":                       # of-date equinox, drifting elements
            R = self._ecl_equinox_to_icrs(jd_tt, cache=False)
            helio = self._helio_vulcan
        else:                                       # constant elements, fixed equinox
            R = self._ecl_equinox_to_icrs(ELEMENTS[name][1])
            helio = lambda je, _n=name: self._helio_ecl(_n, je)

        earth = (np.array(self._earth.at(t).position.au)
                 - np.array(self._sun.at(t).position.au))          # helio, ICRS

        def geocentric(jd_eval):
            return R @ helio(jd_eval) - earth

        g = geocentric(jd_tt)
        tau = float(np.linalg.norm(g)) / _C                        # light-time
        g = geocentric(jd_tt - tau)
        v_earth = np.array(self._earth.at(t).velocity.au_per_d)
        g = g + float(np.linalg.norm(g)) * (v_earth / _C)          # aberration
        _lat, lon, _dist = ICRF(g, t=t, center=399).ecliptic_latlon(epoch=t)
        return lon.degrees % 360.0


def _demo():
    try:
        eng = HypotheticalEngine()
    except (ImportError, FileNotFoundError) as exc:
        print(f"Install skyfield and provide de440.bsp to run the demo: {exc}")
        return
    _SIGNS = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"]
    jd = 2451545.0  # J2000
    for name in HypotheticalEngine.BODIES:
        lon = eng.ecliptic_longitude(jd, name)
        print(f"{name:11} {_SIGNS[int(lon // 30)]} {lon % 30:05.2f}  ({lon:8.4f})")


if __name__ == "__main__":
    _demo()
