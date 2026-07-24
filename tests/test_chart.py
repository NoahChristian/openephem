from openephem import chart, timeplace


def _moment(time_known=True):
    return timeplace.ResolvedMoment(
        jd_ut=2451545.0, lat=40.0, lon=-75.0, tz="UTC", offset_hours=0.0,
        utc_iso=None, time_known=time_known, address=None, warnings=[])


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


def test_points_and_lots(monkeypatch):
    _patch_engines(monkeypatch)
    c = chart.assemble(_moment(), house_system="WholeSign",
                       bodies=["Sun", "Moon", "Ascendant", "Descendant", "ImumCoeli",
                               "Vertex", "EastPoint", "AriesPoint", "LibraPoint",
                               "CoAscendant", "SouthNode", "PartOfFortune"])
    for pt in ("Ascendant", "Descendant", "ImumCoeli", "Vertex", "EastPoint",
               "AriesPoint", "LibraPoint", "CoAscendant", "SouthNode", "PartOfFortune"):
        assert pt in c["bodies"], pt
    assert c["bodies"]["AriesPoint"]["lon"] == 0.0
    assert c["bodies"]["LibraPoint"]["lon"] == 180.0
    assert c["bodies"]["PartOfFortune"]["sect"] in ("day", "night")


class _FakeStarEng:
    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, entry):
        return 50.3        # ~0.3 deg from the fake Sun (50) -> exercises the conjunction pass


def test_fixed_stars(monkeypatch):
    _patch_engines(monkeypatch)
    monkeypatch.setattr("openephem.fixed_stars.SkyfieldFixedStarEngine", _FakeStarEng)
    c = chart.assemble(_moment(), bodies=["Sun", "Regulus"])
    assert c["bodies"]["Regulus"]["kind"] == "star"
    assert "star_aspects" in c
    assert any(sa["star"] == "Regulus" and sa["body"] == "Sun" for sa in c["star_aspects"])


class _FakeHypo:
    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd, name):
        return 123.0


def test_hypothetical_routing(monkeypatch):
    _patch_engines(monkeypatch)
    monkeypatch.setattr("openephem.hypothetical.HypotheticalEngine", _FakeHypo)
    c = chart.assemble(_moment(), bodies=["Cupido"])
    assert c["bodies"]["Cupido"]["lon"] == 123.0


def test_unknown_time_omits_houses(monkeypatch):
    _patch_engines(monkeypatch)
    c = chart.assemble(_moment(time_known=False), bodies=["Sun"])
    assert c["angles"] is None and c["cusps"] is None
    assert any("birth time" in w for w in c["warnings"])


def test_unknown_body_warns(monkeypatch):
    _patch_engines(monkeypatch)
    c = chart.assemble(_moment(), bodies=["Sun", "Nonexistent"])
    assert any("unknown body" in w for w in c["warnings"])
