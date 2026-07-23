import importlib.util
import pytest
from openephem import houses

_HAS_SWE = importlib.util.find_spec("swisseph") is not None
requires_swe = pytest.mark.skipif(not _HAS_SWE, reason="pyswisseph (AGPL) not installed")

SYSTEMS = ["Placidus", "Koch", "Regiomontanus", "Campanus",
           "WholeSign", "Equal", "Porphyry"]
CASES = [(100.0, 23.4367, 51.5), (280.0, 23.4367, 40.7),
         (15.0, 23.44, 60.0), (340.0, 23.44, -45.0)]


def sep(a, b):
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


# Systems where cusp 1 == Asc and cusp 10 == MC by construction (the quadrant
# systems + Porphyry). Whole Sign / Equal deliberately let the MC/Asc float.
ANCHORED = ["Placidus", "Koch", "Regiomontanus", "Campanus", "Porphyry"]


@pytest.mark.parametrize("system", SYSTEMS)
@pytest.mark.parametrize("armc,eps,phi", CASES)
def test_invariants(system, armc, eps, phi):
    h = houses.compute(armc, eps, phi, system)
    c = h.cusps
    assert len(c) == 12
    for i in range(6):                      # opposite cusps are 180 apart
        assert sep((c[i] + 180.0) % 360.0, c[i + 6]) < 1e-6
    for i in range(12):                     # strictly increasing around the wheel
        gap = (c[(i + 1) % 12] - c[i]) % 360.0
        assert 0.0 < gap < 180.0


@pytest.mark.parametrize("system", ANCHORED)
@pytest.mark.parametrize("armc,eps,phi", CASES)
def test_angles_anchored(system, armc, eps, phi):
    h = houses.compute(armc, eps, phi, system)
    assert sep(h.cusps[0], h.asc) < 1e-6    # cusp 1 == Ascendant
    assert sep(h.cusps[9], h.mc) < 1e-6     # cusp 10 == MC


def test_wholesign_and_equal():
    h = houses.compute(100.0, 23.4367, 51.5, "WholeSign")
    base = int(h.asc // 30) * 30
    assert all(sep(h.cusps[i], (base + 30 * i) % 360) < 1e-6 for i in range(12))
    e = houses.compute(100.0, 23.4367, 51.5, "Equal")
    assert all(sep(e.cusps[i], (e.asc + 30 * i) % 360) < 1e-6 for i in range(12))


def test_unknown_system():
    with pytest.raises(KeyError):
        houses.compute(100.0, 23.4367, 51.5, "Nonexistent")


@requires_swe
@pytest.mark.parametrize("system,code",
                         [("Placidus", b"P"), ("Koch", b"K"),
                          ("Regiomontanus", b"R"), ("Campanus", b"C")])
@pytest.mark.parametrize("armc,eps,phi", CASES)
def test_matches_swisseph(system, code, armc, eps, phi):
    import swisseph as swe
    cusps, _ = swe.houses_armc(armc, phi, eps, code)
    h = houses.compute(armc, eps, phi, system)
    for i in range(12):
        assert sep(h.cusps[i], cusps[i]) * 3600.0 < 1.0   # < 1 arcsec
