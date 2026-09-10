import pytest

from openephem import chart, timeplace
from openephem.decennials import (
    CHALDEAN,
    DECENNIAL_MONTHS,
    MINOR_YEARS,
    decennials,
)
from openephem.profections import _calendar_to_jd as jd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

def test_minor_years_and_decennial_length():
    assert set(MINOR_YEARS) == set(CHALDEAN)
    assert MINOR_YEARS == {"Saturn": 30, "Jupiter": 12, "Mars": 15, "Sun": 19,
                           "Venus": 8, "Mercury": 20, "Moon": 25}
    assert DECENNIAL_MONTHS == 129                       # 10 years 9 months
    assert CHALDEAN == ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]


# --------------------------------------------------------------------------- #
# Pure module
# --------------------------------------------------------------------------- #

def test_start_validation():
    with pytest.raises(ValueError):
        decennials("North Node", jd(1990, 1, 1))


def test_seven_decennials_each_10y9m_in_chaldean_order():
    tl = decennials("Saturn", jd(1970, 9, 14), horizon_years=75.25)["timeline"]
    assert len(tl) == 7
    assert [b["ruler"] for b in tl] == CHALDEAN            # succession from Saturn
    for b in tl:
        assert abs((b["age_end"] - b["age_start"]) - 10.75) < 0.02   # 10y 9m each


def test_subs_start_with_general_ruler_and_cycle():
    tl = decennials("Venus", jd(2000, 1, 1), horizon_years=11)["timeline"]
    first = tl[0]
    assert first["ruler"] == "Venus"
    subs = [s["ruler"] for s in first["subs"]]
    vi = CHALDEAN.index("Venus")
    assert subs == [CHALDEAN[(vi + j) % 7] for j in range(7)]   # Venus, then Chaldean cycle
    assert len(subs) == 7


def test_sub_lengths_are_minor_years_in_months():
    b = decennials("Saturn", jd(1970, 9, 14), horizon_years=11)["timeline"][0]
    # Saturn sub = 30 months; the whole decennial = 129 months. Check the first sub's span
    # is ~30/129 of the decennial.
    from openephem.profections import _calendar_to_jd as _j
    span = _j(*[int(x) for x in b["end"].split("-")]) - _j(*[int(x) for x in b["start"].split("-")])
    s0 = b["subs"][0]
    sub_span = _j(*[int(x) for x in s0["end"].split("-")]) - _j(*[int(x) for x in s0["start"].split("-")])
    assert abs(sub_span / span - 30 / 129) < 0.01


def test_current_major_and_sub():
    r = decennials("Saturn", jd(1970, 9, 14), jd(2026, 6, 1))
    assert r["age"] == 55 and r["start"] == "Saturn"
    cur = r["current"]
    # age 55 falls in the Mercury decennial (53.75–64.50), Moon sub-period
    assert cur["major"] == "Mercury" and cur["sub"] == "Moon"
    assert cur["sub_start"] <= r["as_of"] < cur["sub_end"]
    assert cur["major_start"] <= r["as_of"] < cur["major_end"]


def test_cycle_repeats_after_75_years():
    tl = decennials("Sun", jd(2000, 1, 1), jd(2090, 1, 1))["timeline"]
    assert len(tl) >= 8 and tl[7]["ruler"] == tl[0]["ruler"]   # 8th decennial == 1st


# --------------------------------------------------------------------------- #
# assemble() integration
# --------------------------------------------------------------------------- #

class _FakePlanet:
    _LON = {"Sun": 50.0, "Moon": 200.0, "Mercury": 45.0, "Venus": 70.0, "Mars": 100.0,
            "Jupiter": 150.0, "Saturn": 250.0, "Uranus": 300.0, "Neptune": 330.0,
            "Pluto": 280.0, "TrueNode": 10.0, "MeanLilith": 20.0}

    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, name):
        return self._LON[name]


class _FakeAst:
    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, name):
        return 15.0


def _moment(time_known=True):
    return timeplace.ResolvedMoment(
        jd_ut=2451545.0, lat=40.0, lon=-75.0, tz="UTC", offset_hours=0.0,
        utc_iso=None, time_known=time_known, address=None, warnings=[])


def _patch(mp):
    mp.setattr("openephem.planets_skyfield.SkyfieldPlanetEngine", _FakePlanet)
    mp.setattr("openephem.asteroids_skyfield.SkyfieldAsteroidEngine", _FakeAst)


def test_assemble_decennials_default_from_fortune(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), decennials_as_of=(2030, 1, 1))
    d = c["decennials"]
    assert d["start"] in MINOR_YEARS
    assert d["timeline"] and "current" in d
    assert d["current"]["major"] in MINOR_YEARS


def test_assemble_decennials_explicit_start(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), decennials_as_of=(2030, 1, 1), decennials_start="Mars")
    assert c["decennials"]["start"] == "Mars"
    assert c["decennials"]["timeline"][0]["ruler"] == "Mars"


def test_assemble_decennials_bad_start_warns(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), decennials_as_of=(2030, 1, 1), decennials_start="Chiron")
    assert "decennials" not in c
    assert any("Chiron" in w for w in c["warnings"])


def test_assemble_decennials_houseless_needs_start(monkeypatch):
    _patch(monkeypatch)
    # no birth time -> can't find the Lot of Fortune's ruler, so it's omitted…
    c = chart.assemble(_moment(time_known=False), decennials_as_of=(2030, 1, 1))
    assert "decennials" not in c and any("decennials" in w for w in c["warnings"])
    # …unless the caller supplies the starting planet explicitly
    c2 = chart.assemble(_moment(time_known=False), decennials_as_of=(2030, 1, 1),
                        decennials_start="Jupiter")
    assert c2["decennials"]["start"] == "Jupiter"


def test_assemble_no_decennials_by_default(monkeypatch):
    _patch(monkeypatch)
    assert "decennials" not in chart.assemble(_moment())
