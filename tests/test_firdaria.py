import pytest

from openephem import chart, timeplace
from openephem.firdaria import _DAY_ORDER, _NIGHT_ORDER, firdaria
from openephem.profections import _calendar_to_jd as jd


# --------------------------------------------------------------------------- #
# Pure module
# --------------------------------------------------------------------------- #

def test_orders_total_75_and_heads():
    assert sum(y for _, y in _DAY_ORDER) == 75
    assert sum(y for _, y in _NIGHT_ORDER) == 75
    assert _DAY_ORDER[0][0] == "Sun" and _NIGHT_ORDER[0][0] == "Moon"


def test_sect_validation():
    with pytest.raises(ValueError):
        firdaria(jd(1990, 1, 1), "twilight")


def test_timeline_and_current():
    f = firdaria(jd(1970, 9, 14), "night", jd(2026, 6, 1), horizon_years=80)
    assert f["sect"] == "night" and f["age"] == 55
    tl = f["timeline"]
    assert tl[0]["ruler"] == "Moon" and tl[0]["age_start"] == 0.0
    assert abs(tl[0]["age_end"] - 9.0) < 0.02          # Moon = 9 years
    assert f["current"]["major"] == "Venus" and f["current"]["sub"] == "Mars"
    assert f["current"]["sub_start"] <= f["as_of"] < f["current"]["sub_end"]


def test_planetary_subs_start_with_ruler():
    moon = firdaria(jd(1970, 9, 14), "night", horizon_years=20)["timeline"][0]
    subs = [s["ruler"] for s in moon["subs"]]
    assert len(subs) == 7 and subs[0] == "Moon"


def test_nodes_subdivided_default_and_off():
    on = firdaria(jd(2000, 1, 1), "day", horizon_years=76)
    node = next(b for b in on["timeline"] if b["ruler"] == "North Node")
    assert len(node["subs"]) == 7 and node["subs"][0]["ruler"] == "Sun"   # day head
    off = firdaria(jd(2000, 1, 1), "day", horizon_years=76, subdivide_nodes=False)
    node_off = next(b for b in off["timeline"] if b["ruler"] == "North Node")
    assert node_off.get("subs", []) == []


def test_cycle_repeats_after_75():
    rulers = [b["ruler"] for b in firdaria(jd(2000, 1, 1), "day", horizon_years=85)["timeline"]]
    assert rulers[0] == "Sun" and rulers.count("Sun") >= 2   # Sun period recurs


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


def test_assemble_firdaria(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), firdaria_as_of=(2030, 1, 1))
    f = c["firdaria"]
    assert f["sect"] in ("day", "night")
    assert f["timeline"] and "current" in f
    assert f["current"]["major"] in {n for n, _ in _DAY_ORDER}


def test_assemble_firdaria_houseless_omitted(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(time_known=False), firdaria_as_of=(2030, 1, 1))
    assert "firdaria" not in c
    assert any("firdaria" in w for w in c["warnings"])


def test_assemble_no_firdaria_by_default(monkeypatch):
    _patch(monkeypatch)
    assert "firdaria" not in chart.assemble(_moment())
