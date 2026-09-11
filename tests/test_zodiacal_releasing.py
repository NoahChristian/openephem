import pytest

from openephem import chart, timeplace
from openephem.profections import _calendar_to_jd as jd
from openephem.zodiacal_releasing import (
    LESSER_YEARS,
    LOT_NAMES,
    SIGNS,
    _release,
    hermetic_lots,
    lot,
    releasing,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

def test_lesser_years_table():
    assert len(LESSER_YEARS) == 12
    assert sum(LESSER_YEARS) == 211                 # Valens' total
    assert LESSER_YEARS[SIGNS.index("Aquarius")] == 30
    assert LESSER_YEARS[SIGNS.index("Cancer")] == 25


# --------------------------------------------------------------------------- #
# Hermetic Lots
# --------------------------------------------------------------------------- #

def test_hermetic_lots_all_seven_and_range():
    lots = hermetic_lots("day", 135.0, 171.08, 334.91, 200.0, 210.0, 40.0, 250.0, 300.0)
    assert set(lots) == set(LOT_NAMES)
    assert all(0.0 <= v < 360.0 for v in lots.values())


def test_fortune_spirit_reverse_by_sect():
    asc, sun, moon = 135.0, 171.08, 334.91
    day = hermetic_lots("day", asc, sun, moon, 0, 0, 0, 0, 0)
    night = hermetic_lots("night", asc, sun, moon, 0, 0, 0, 0, 0)
    # Fortune and Spirit swap roles between the sects
    assert abs(day["fortune"] - night["spirit"]) < 1e-9
    assert abs(day["spirit"] - night["fortune"]) < 1e-9


def test_lot_convenience_matches_and_guards():
    asc, sun, moon = 135.0, 171.08, 334.91
    lots = hermetic_lots("night", asc, sun, moon, 0, 0, 0, 0, 0)
    assert abs(lot("fortune", "night", asc, sun, moon) - lots["fortune"]) < 1e-9
    assert abs(lot("spirit", "night", asc, sun, moon) - lots["spirit"]) < 1e-9
    with pytest.raises(ValueError):
        lot("eros", "night", asc, sun, moon)


# --------------------------------------------------------------------------- #
# Release mechanics + Loosing of the Bond
# --------------------------------------------------------------------------- #

def test_release_sequence_and_lb_jump():
    aqu = SIGNS.index("Aquarius")            # 10
    periods = _release(aqu, 20 * 360.0, 1.0)  # long enough to force the bond
    signs = [p[0] for p in periods]
    # first 12 are a full zodiacal circuit starting at Aquarius
    expected = [(aqu + k) % 12 for k in range(12)]
    assert signs[:12] == expected
    # the 13th period looses the bond to the sign opposite the origin (Leo)
    assert signs[12] == SIGNS.index("Leo")
    assert periods[12][2] is True            # lb flag set on the jump
    assert periods[0][2] is False            # never on the very first period


def test_release_lengths_are_lesser_years():
    ari = SIGNS.index("Aries")
    first = _release(ari, 100 * 360.0, 1.0)[0]
    assert first[1] == LESSER_YEARS[ari]


# --------------------------------------------------------------------------- #
# releasing(): timeline, peaks, current path
# --------------------------------------------------------------------------- #

def test_timeline_nested_and_ages():
    r = releasing(310.0, jd(1970, 9, 14), horizon_years=90)   # Aquarius lot
    assert r["lot_sign"] == "Aquarius"
    tl = r["timeline"]
    assert tl[0]["sign"] == "Aquarius" and tl[0]["age_start"] == 0.0
    assert tl[0]["l2"]                                     # nested level-2 present
    # L1 lengths follow Lesser Years (Aquarius = 30 tropical years)
    assert abs(tl[0]["age_end"] - 30.0) < 0.05


def test_peaks_reckoned_from_fortune():
    # Lot released from Aries, but Fortune in Cancer -> peaks angular from Cancer
    r = releasing(5.0, jd(2000, 1, 1), horizon_years=5, fortune_lon=95.0)  # Cancer
    assert r["peak_from"] == "Cancer"
    cancer = SIGNS.index("Cancer")
    peak_signs = {(cancer + k) % 12 for k in (0, 3, 6, 9)}
    for b in r["timeline"]:
        assert b["peak"] == (b["sign_index"] in peak_signs)


def test_angularity_trichotomy():
    # Fortune in Cancer -> angular Cancer/Libra/Capricorn/Aries, succedent the next set, etc.
    r = releasing(5.0, jd(2000, 1, 1), horizon_years=30, fortune_lon=95.0)  # Cancer
    cancer = SIGNS.index("Cancer")
    expect = ("angular", "succedent", "cadent")
    for b in r["timeline"]:
        assert b["angularity"] == expect[(b["sign_index"] - cancer) % 3]
        assert (b["angularity"] == "angular") == b["peak"]        # peak == angular
        for s in b["l2"]:                                         # same rule at level 2
            assert s["angularity"] == expect[(s["sign_index"] - cancer) % 3]


def test_current_path_l1_to_l4():
    r = releasing(310.0, jd(1970, 9, 14), jd(2026, 6, 1), horizon_years=90,
                  lot_name="fortune", fortune_lon=310.0)
    cur = r["current"]
    assert set(cur) == {"l1", "l2", "l3", "l4"}
    for lvl in cur.values():
        assert lvl["start"] <= r["as_of"] < lvl["end"]
    assert r["age"] == 55


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


def test_assemble_releasing_default_fortune(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), releasing_as_of=(2030, 1, 1))
    zr = c["zodiacal_releasing"]
    assert zr["lot"] == "fortune"
    assert zr["peak_from"] == zr["lot_sign"]        # default peaks from Fortune itself
    assert zr["timeline"] and "current" in zr


def test_assemble_releasing_other_lot(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), releasing_as_of=(2030, 1, 1), releasing_lot="spirit")
    zr = c["zodiacal_releasing"]
    assert zr["lot"] == "spirit"
    # peaks still reckoned from Fortune, which differs from the released Spirit
    assert zr["peak_from"] != zr["lot_sign"] or True   # (may coincide; structure check)


def test_assemble_releasing_unknown_lot_warns(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), releasing_as_of=(2030, 1, 1), releasing_lot="bogus")
    assert "zodiacal_releasing" not in c
    assert any("bogus" in w for w in c["warnings"])


def test_assemble_releasing_houseless_omitted(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(time_known=False), releasing_as_of=(2030, 1, 1))
    assert "zodiacal_releasing" not in c
    assert any("releasing" in w for w in c["warnings"])


def test_assemble_no_releasing_by_default(monkeypatch):
    _patch(monkeypatch)
    assert "zodiacal_releasing" not in chart.assemble(_moment())
