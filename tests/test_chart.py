from openephem import chart, timeplace


def _moment():
    return timeplace.ResolvedMoment(
        jd_ut=2451545.0, lat=40.0, lon=-75.0, tz="UTC", offset_hours=0.0,
        utc_iso=None, time_known=True, address=None, warnings=[])


class _FakePlanet:
    _LON = {"Sun": 50.0, "Moon": 200.0, "Mercury": 45.0, "Venus": 70.0,
            "Mars": 100.0, "Jupiter": 150.0, "Saturn": 250.0, "Uranus": 300.0,
            "Neptune": 330.0, "Pluto": 280.0, "TrueNode": 10.0, "MeanLilith": 20.0}

    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, name):
        return self._LON[name]


class _FakeAst:
    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, name):
        return 15.0


def _patch_engines(mp):
    mp.setattr("openephem.planets_skyfield.SkyfieldPlanetEngine", _FakePlanet)
    mp.setattr("openephem.asteroids_skyfield.SkyfieldAsteroidEngine", _FakeAst)


def test_tropical_chart(monkeypatch):
    _patch_engines(monkeypatch)
    c = chart.assemble(_moment(), house_system="Placidus")
    assert c["zodiac"] == "tropical"
    assert c["angles"] and len(c["cusps"]) == 12
    assert c["bodies"]["Sun"]["sign"] == "Taurus"        # 50 deg -> Taurus
    assert "Chiron" in c["bodies"]


def test_sidereal_chart(monkeypatch):
    _patch_engines(monkeypatch)
    c = chart.assemble(_moment(), zodiac="sidereal", ayanamsa="lahiri")
    assert c["zodiac"] == "sidereal"
    assert c["ayanamsa"]["system"] == "lahiri"
    sun = c["bodies"]["Sun"]
    assert "nakshatra" in sun
    assert sun["sign"] == "Mesha"                        # 50 - ~23.86 -> Aries/Mesha


def test_graceful_when_engines_fail(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no ephemeris data")
    monkeypatch.setattr("openephem.planets_skyfield.SkyfieldPlanetEngine", _Boom)
    monkeypatch.setattr("openephem.asteroids_skyfield.SkyfieldAsteroidEngine", _Boom)
    c = chart.assemble(_moment())
    assert len(c["bodies"]) == 0                          # no bodies...
    assert c["angles"] and len(c["cusps"]) == 12          # ...but houses still work
    assert any("unavailable" in w for w in c["warnings"])
