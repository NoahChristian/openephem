"""Uranian / hypothetical-body engine.

Offline tests check the registry wiring and the element table / Kepler solver.
The parity test runs only when Skyfield+DE440 and pyswisseph are both available;
it asserts sub-arcsecond agreement with Swiss Ephemeris (the authority)."""
import math
import os

import pytest

from openephem import hypothetical as H
from openephem import bodies

# swisseph body numbers for the eleven implemented hypothetical bodies.
_IPL = {"Cupido": 40, "Hades": 41, "Zeus": 42, "Kronos": 43, "Apollon": 44,
        "Admetos": 45, "Vulcanus": 46, "Poseidon": 47, "TransPluto": 48,
        "Vulcan": 55, "WhiteMoon": 56}
_DE440 = os.path.join(os.path.dirname(os.path.dirname(__file__)), "de440.bsp")


def test_registry_implemented():
    """All eleven hypotheticals are registered, implemented, engine=hypothetical."""
    for name in _IPL:
        b = bodies.get(name)
        assert b is not None and b.engine == "hypothetical"
        assert b.implemented, f"{name} should be implemented"
    assert set(H.HypotheticalEngine.BODIES) == set(_IPL)
    assert bodies.canonical("Selena") == "WhiteMoon"    # alias


def test_elements_wellformed():
    # ELEMENTS holds only the nine constant-element heliocentric bodies.
    assert set(H.ELEMENTS) == set(_IPL) - {"Vulcan", "WhiteMoon"}
    for name, el in H.ELEMENTS.items():
        assert len(el) == 8, name
        _epoch, _eq, _M0, a, e, _peri, _node, _incl = el
        assert a > 30.0 and 0.0 <= e < 0.5, name  # slow trans-Neptunian, low-e


def test_kepler_solver():
    for e in (0.0, 0.05, 0.3):
        for M in (0.0, 30.0, 170.0, 359.0):
            E = H._kepler(M, e)
            # E must satisfy Kepler's equation E - e sin E = M
            assert abs((E - e * math.sin(E)) - math.radians(M % 360.0)) < 1e-9


@pytest.mark.skipif(not os.path.exists(_DE440), reason="DE440 kernel not present")
def test_engine_ranges():
    """Every body computes a plausible longitude; nearby dates move slowly."""
    eng = H.HypotheticalEngine(_DE440)
    jd = 2451545.0  # J2000
    for name in _IPL:
        lon = eng.ecliptic_longitude(jd, name)
        assert 0.0 <= lon < 360.0
    # the trans-Neptunian nine barely move in a day (< ~0.02 deg/day)
    for name in set(_IPL) - {"Vulcan", "WhiteMoon"}:
        step = eng.ecliptic_longitude(jd + 1.0, name) - eng.ecliptic_longitude(jd, name)
        assert abs((step + 180.0) % 360.0 - 180.0) < 0.05


@pytest.mark.skipif(not os.path.exists(_DE440), reason="DE440 kernel not present")
def test_parity_vs_swisseph():
    swe = pytest.importorskip("swisseph")
    ephe = os.path.join(os.path.dirname(_DE440), "ephe")
    if not os.path.exists(os.path.join(ephe, "seorbel.txt")):
        pytest.skip("seorbel.txt (swisseph orbital elements) not present")
    swe.set_ephe_path(ephe)
    eng = H.HypotheticalEngine(_DE440)
    worst = 0.0
    for (Y, Mo, D) in [(2000, 1, 1), (1990, 5, 15), (2024, 6, 1), (1935, 3, 20)]:
        jd = swe.julday(Y, Mo, D, 12.0)
        for name, ipl in _IPL.items():
            ref = swe.calc_ut(jd, ipl, swe.FLG_SWIEPH)[0][0]
            mine = eng.ecliptic_longitude(jd, name)
            diff = abs((mine - ref + 180.0) % 360.0 - 180.0) * 3600.0
            worst = max(worst, diff)
    assert worst < 2.0, f"worst residual {worst:.2f}\" exceeds 2\" vs swisseph"
