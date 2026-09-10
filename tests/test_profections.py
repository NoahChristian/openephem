import pytest

from openephem import chart, timeplace
from openephem import profections as prof

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

jd = prof._calendar_to_jd


# --------------------------------------------------------------------------- #
# Pure module — no engines, no data
# --------------------------------------------------------------------------- #

def test_age_zero_is_rising_sign():
    p = prof.annual_profection(130.0, 0)          # 130 deg -> Leo rising
    assert p["profected_house"] == 1
    assert p["profected_sign"] == "Leo"
    assert p["ruler"] == "Sun"
    assert p["profected_sign_lon"] == 120.0        # Leo starts at 120 deg


def test_house_advances_one_sign_per_year():
    asc = 130.0                                    # Leo
    assert prof.annual_profection(asc, 1)["profected_sign"] == "Virgo"
    assert prof.annual_profection(asc, 1)["profected_house"] == 2
    # 34 % 12 == 10 -> 11th place, 10 signs on from Leo = Gemini (Mercury)
    p = prof.annual_profection(asc, 34)
    assert (p["profected_house"], p["profected_sign"], p["ruler"]) == (11, "Gemini", "Mercury")


def test_twelve_year_cycle_wraps():
    for age in (0, 12, 24, 120):
        p = prof.annual_profection(200.0, age)     # 200 deg -> Libra
        assert p["profected_house"] == 1
        assert p["profected_sign"] == "Libra"


def test_traditional_rulers():
    # profections are traditional: Mars/Scorpio, Saturn/Aquarius, Jupiter/Pisces
    assert prof.DOMICILE_RULER["Scorpio"] == "Mars"
    assert prof.DOMICILE_RULER["Aquarius"] == "Saturn"
    assert prof.DOMICILE_RULER["Pisces"] == "Jupiter"
    assert set(prof.DOMICILE_RULER) == set(SIGNS)
    assert set(prof.DOMICILE_RULER.values()) == {
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}


def test_negative_age_rejected():
    with pytest.raises(ValueError):
        prof.annual_profection(0.0, -1)


def test_calendar_roundtrip():
    for y, m, d in [(1990, 5, 15), (2000, 1, 1), (1582, 10, 4), (-100, 7, 1)]:
        assert prof._jd_to_calendar(jd(y, m, d)) == (y, m, d)


def test_completed_years_turns_on_birthday():
    birth = jd(1990, 5, 15)
    assert prof.completed_years(birth, jd(2023, 5, 14)) == 32   # day before b'day
    assert prof.completed_years(birth, jd(2023, 5, 15)) == 33   # on the birthday
    assert prof.completed_years(birth, birth) == 0
    assert prof.completed_years(birth, jd(1989, 1, 1)) == 0     # never negative


def test_profection_year_bounds():
    birth = jd(1990, 5, 15)
    start, nxt, age = prof.profection_year_bounds(birth, jd(2025, 1, 1))
    # as-of 2025-01-01 -> current year runs 2024-05-15 .. 2025-05-15, age 34
    assert prof._jd_to_calendar(start) == (2024, 5, 15)
    assert prof._jd_to_calendar(nxt) == (2025, 5, 15)
    assert age == 34


def test_full_profection_structure_and_bounds():
    p = prof.full_profection(169.46, jd(1990, 5, 15), jd(2025, 1, 1))  # Virgo rising
    assert p["method"] == "annual+monthly+daily"
    assert (p["age"], p["profected_house"], p["profected_sign"], p["ruler"]) \
        == (34, 11, "Cancer", "Moon")                # Lord of the Year
    for key in ("monthly", "daily"):
        b = p[key]
        assert 0 <= b["index"] <= 11
        assert b["profected_sign"] in SIGNS
        assert b["ruler"] == prof.DOMICILE_RULER[b["profected_sign"]]
        # the as-of date must fall inside each sub-period
        assert b["period_start"] <= "2025-01-01" <= b["period_end"]


def test_monthly_daily_start_on_annual_sign_at_birthday():
    # at the exact birthday, month 0 and day 0 -> both equal the annual sign
    birth = jd(1990, 5, 15)
    p = prof.full_profection(169.46, birth, jd(2024, 5, 15))   # a birthday, age 34
    assert p["monthly"]["index"] == 0 and p["daily"]["index"] == 0
    assert p["monthly"]["profected_sign"] == p["profected_sign"]
    assert p["daily"]["profected_sign"] == p["profected_sign"]


def test_monthly_advances_one_sign_per_month():
    birth = jd(1990, 5, 15)
    asc = 169.46                                    # Virgo rising, annual (age 34) = Cancer
    p0 = prof.full_profection(asc, birth, jd(2024, 5, 15))      # month 0
    # ~1.2 months later lands in month 1, one sign on from the annual sign
    p1 = prof.full_profection(asc, birth, jd(2024, 6, 20))
    i0 = p0["monthly"]["profected_sign_index"]
    i1 = p1["monthly"]["profected_sign_index"]
    assert p1["monthly"]["index"] == 1
    assert i1 == (i0 + 1) % 12


def test_profection_for_dispatch():
    a = prof.profection_for(130.0, age=33)
    assert a["method"] == "annual"
    f = prof.profection_for(130.0, jd_birth=jd(1990, 5, 15), jd_asof=jd(2024, 1, 1))
    assert f["method"] == "annual+monthly+daily"
    assert a["profected_sign"] == f["profected_sign"]           # same annual place
    with pytest.raises(ValueError):
        prof.profection_for(130.0)


# --------------------------------------------------------------------------- #
# assemble() integration (fake engines; jd_ut = J2000 = 2000-01-01)
# --------------------------------------------------------------------------- #

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


def _moment(time_known=True):
    return timeplace.ResolvedMoment(
        jd_ut=2451545.0, lat=40.0, lon=-75.0, tz="UTC", offset_hours=0.0,
        utc_iso=None, time_known=time_known, address=None, warnings=[])


def _patch(mp):
    mp.setattr("openephem.planets_skyfield.SkyfieldPlanetEngine", _FakePlanet)
    mp.setattr("openephem.asteroids_skyfield.SkyfieldAsteroidEngine", _FakeAst)


def test_assemble_age_only_is_annual(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), profection_age=0)
    p = c["profections"]
    asc_sign = SIGNS[int(c["angles"]["asc"] // 30)]
    assert p["method"] == "annual" and "monthly" not in p
    assert p["profected_house"] == 1 and p["profected_sign"] == asc_sign
    assert p["ruler"] == prof.DOMICILE_RULER[asc_sign]
    # Lord-of-the-Year natal placement attached as positional data
    assert "ruler_lon" in p and "ruler_sign" in p and 1 <= p["ruler_house"] <= 12


def test_assemble_as_of_is_full_set(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), profection_as_of=(2024, 6, 1))   # born 2000-01-01
    p = c["profections"]
    assert p["method"] == "annual+monthly+daily"
    assert p["age"] == 24 and p["as_of"] == "2024-06-01"
    for key in ("monthly", "daily"):
        b = p[key]
        assert b["ruler"] == prof.DOMICILE_RULER[b["profected_sign"]]
        assert b["period_start"] <= "2024-06-01" <= b["period_end"]
        assert "ruler_sign" in b            # lord placement enriched too


def test_assemble_no_profection_by_default(monkeypatch):
    _patch(monkeypatch)
    assert "profections" not in chart.assemble(_moment())


def test_assemble_houseless_omits_profection(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(time_known=False), profection_age=5)
    assert "profections" not in c
    assert any("profection" in w for w in c["warnings"])


def test_assemble_profection_follows_sidereal_asc(monkeypatch):
    _patch(monkeypatch)
    trop = chart.assemble(_moment(), profection_age=0)
    sid = chart.assemble(_moment(), zodiac="sidereal", profection_age=0)
    assert sid["profections"]["profected_sign"] == SIGNS[int(sid["angles"]["asc"] // 30)]
    assert trop["profections"]["profected_sign"] == SIGNS[int(trop["angles"]["asc"] // 30)]
