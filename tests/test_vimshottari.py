import pytest

from openephem import chart, timeplace
from openephem.profections import _calendar_to_jd as jd
from openephem.vimshottari import SEQUENCE, TOTAL_YEARS, YEARS, vimshottari

_NAK = 360.0 / 27.0


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

def test_sequence_and_years_sum_to_120():
    assert TOTAL_YEARS == 120
    assert sum(YEARS.values()) == 120
    assert SEQUENCE == ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
                        "Jupiter", "Saturn", "Mercury"]
    assert set(YEARS) == set(SEQUENCE)
    assert YEARS == {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
                     "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}


@pytest.mark.parametrize("idx,lord", [
    (0, "Ketu"), (1, "Venus"), (2, "Sun"), (3, "Moon"), (4, "Mars"), (5, "Rahu"),
    (6, "Jupiter"), (7, "Saturn"), (8, "Mercury"), (9, "Ketu"), (26, "Mercury"),
])
def test_nakshatra_lord_mapping(idx, lord):
    # a Moon at the centre of nakshatra `idx` opens the daśā of SEQUENCE[idx % 9]
    lon = (idx + 0.5) * _NAK
    assert vimshottari(lon, jd(2000, 1, 1))["moon_nakshatra"]["lord"] == lord


# --------------------------------------------------------------------------- #
# Balance at birth
# --------------------------------------------------------------------------- #

def test_full_balance_at_nakshatra_start():
    # Moon exactly at 0° (start of Aśvinī, Ketu) → the whole 7-year Ketu daśā remains
    r = vimshottari(0.0, jd(2000, 1, 1))
    assert r["moon_nakshatra"]["lord"] == "Ketu"
    assert r["balance"] == {"lord": "Ketu", "years": 7.0}
    assert r["timeline"][0]["ruler"] == "Ketu"
    assert r["timeline"][0]["age_start"] == 0.0


def test_proportional_balance_mid_nakshatra():
    # halfway through Aśvinī → half of Ketu's 7 years (3.5) remains
    r = vimshottari(_NAK * 0.5, jd(2000, 1, 1))
    assert r["balance"]["lord"] == "Ketu"
    assert abs(r["balance"]["years"] - 3.5) < 1e-6
    # the first Mahādaśā is clipped to that balance
    b0 = r["timeline"][0]
    assert abs((b0["age_end"] - b0["age_start"]) - 3.5) < 0.02


def test_balance_is_plain_float():
    r = vimshottari(123.456, jd(2000, 1, 1))
    assert type(r["balance"]["years"]) is float          # not numpy, JSON-clean


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #

def test_mahadasha_sequence_and_monotonic_ages():
    r = vimshottari(_NAK * 3.5, jd(2000, 1, 1))          # Rohiṇī → Moon opens
    lords = [b["ruler"] for b in r["timeline"]]
    assert lords[0] == "Moon"
    start = SEQUENCE.index("Moon")
    assert lords[:9] == [SEQUENCE[(start + k) % 9] for k in range(9)]
    ages = [b["age_start"] for b in r["timeline"]]
    assert ages[0] == 0.0
    assert all(ages[i] < ages[i + 1] for i in range(len(ages) - 1))


def test_full_mahadasha_has_nine_antardashas_summing_to_its_length():
    # the SECOND Mahādaśā is whole (the first is the clipped balance)
    r = vimshottari(0.0, jd(2000, 1, 1))                  # Ketu balance full, then Venus whole
    second = r["timeline"][1]
    assert second["ruler"] == "Venus"
    assert len(second["subs"]) == 9
    assert second["subs"][0]["ruler"] == "Venus"          # antars open with the maha lord
    seq = [s["ruler"] for s in second["subs"]]
    vi = SEQUENCE.index("Venus")
    assert seq == [SEQUENCE[(vi + k) % 9] for k in range(9)]


def test_antardasha_length_is_maha_times_antar_over_120():
    r = vimshottari(0.0, jd(2000, 1, 1))
    b = r["timeline"][1]                                   # whole Venus maha (20y)
    span = jd(*_d(b["end"])) - jd(*_d(b["start"]))
    s0 = b["subs"][0]                                      # Venus antar in Venus maha
    sub = jd(*_d(s0["end"])) - jd(*_d(s0["start"]))
    assert abs(sub / span - (YEARS["Venus"] / 120.0)) < 0.005


def test_first_mahadasha_antars_clipped_to_birth():
    # mid-nakshatra: the first maha is partial, so it shows fewer than nine antars, all >= birth
    r = vimshottari(_NAK * 3.5, jd(2000, 1, 1))
    b0 = r["timeline"][0]
    assert 0 < len(b0["subs"]) <= 9
    assert b0["subs"][0]["start"] == b0["start"]          # first visible antar opens at birth


def _d(iso):
    return [int(x) for x in iso.split("-")]


# --------------------------------------------------------------------------- #
# current (as-of)
# --------------------------------------------------------------------------- #

def test_current_maha_antar_pratyantar():
    r = vimshottari(45.0, jd(2000, 1, 1), jd(2040, 6, 1))
    assert r["age"] == 40 and r["as_of"] == "2040-06-01"
    cur = r["current"]
    for k in ("maha", "antar", "pratyantar"):
        assert cur[k] in SEQUENCE
    assert cur["maha_start"] <= r["as_of"] < cur["maha_end"]
    assert cur["antar_start"] <= r["as_of"] < cur["antar_end"]
    assert cur["pratyantar_start"] <= r["as_of"] < cur["pratyantar_end"]


# --------------------------------------------------------------------------- #
# assemble() integration (no kernels — patched engines)
# --------------------------------------------------------------------------- #

class _FakePlanet:
    _LON = {"Sun": 50.0, "Moon": 200.0, "Mercury": 45.0, "Venus": 70.0, "Mars": 100.0,
            "Jupiter": 150.0, "Saturn": 250.0, "Uranus": 300.0, "Neptune": 330.0,
            "Pluto": 280.0, "TrueNode": 10.0, "MeanLilith": 20.0}

    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd_ut, name):
        return self._LON[name]


class _FakeAst:
    def __init__(self, *a, **k):
        pass

    def ecliptic_longitude(self, jd_ut, name):
        return 15.0


def _moment(time_known=True):
    return timeplace.ResolvedMoment(
        jd_ut=2451545.0, lat=40.0, lon=-75.0, tz="UTC", offset_hours=0.0,
        utc_iso=None, time_known=time_known, address=None, warnings=[])


def _patch(mp):
    mp.setattr("openephem.planets_skyfield.SkyfieldPlanetEngine", _FakePlanet)
    mp.setattr("openephem.asteroids_skyfield.SkyfieldAsteroidEngine", _FakeAst)


def test_assemble_vimshottari_present(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), vimshottari_as_of=(2040, 6, 1))
    v = c["vimshottari"]
    assert v["system"] == "vimshottari"
    assert v["moon_nakshatra"]["lord"] in SEQUENCE
    assert v["timeline"] and "current" in v
    assert v["ayanamsa"]["system"] == "lahiri"
    assert type(v["balance"]["years"]) is float


def test_assemble_dasha_identical_tropical_and_sidereal(monkeypatch):
    _patch(monkeypatch)
    vt = chart.assemble(_moment(), zodiac="tropical", vimshottari_as_of=(2040, 6, 1))["vimshottari"]
    vs = chart.assemble(_moment(), zodiac="sidereal", vimshottari_as_of=(2040, 6, 1))["vimshottari"]
    # both key off the sidereal Moon, so the daśā is the same in either zodiac
    assert vt["timeline"] == vs["timeline"]
    assert vt["current"] == vs["current"]


def test_assemble_unknown_time_warns_but_computes(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(time_known=False), vimshottari_as_of=(2040, 6, 1))
    assert "vimshottari" in c                              # still computed from the Moon
    assert any("vimshottari" in w.lower() for w in c["warnings"])


# --------------------------------------------------------------------------- #
# levels, year convention, lord enrichment
# --------------------------------------------------------------------------- #

def test_levels_nest_deeper():
    # levels=3 → Antardaśās carry Pratyantardaśās; levels=2 → they don't
    a3 = vimshottari(45.0, jd(2000, 1, 1), levels=3)["timeline"][1]["subs"][0]
    a2 = vimshottari(45.0, jd(2000, 1, 1), levels=2)["timeline"][1]["subs"][0]
    assert "subs" in a3 and len(a3["subs"]) == 9
    assert "subs" not in a2


def test_default_year_is_solar_sidereal():
    from openephem.vimshottari import SIDEREAL_YEAR, YEAR
    assert YEAR == SIDEREAL_YEAR == 365.256363


def test_year_length_scales_periods():
    # a whole Mahādaśā under a 360-day sāvana year is shorter than under the sidereal default
    sid = vimshottari(0.0, jd(2000, 1, 1))["timeline"][1]            # whole Venus (20y)
    sav = vimshottari(0.0, jd(2000, 1, 1), year_length=360.0)["timeline"][1]
    span_sid = jd(*_d(sid["end"])) - jd(*_d(sid["start"]))
    span_sav = jd(*_d(sav["end"])) - jd(*_d(sav["start"]))
    assert span_sid > span_sav
    assert abs(span_sav - 20 * 360.0) < 1.0                          # 20 sāvana years


def test_assemble_lords_natal_placement(monkeypatch):
    _patch(monkeypatch)
    c = chart.assemble(_moment(), vimshottari_as_of=(2040, 6, 1))
    lords = c["vimshottari"]["lords"]
    assert set(lords) == set(SEQUENCE)                    # all nine grahas placed
    for pl in lords.values():
        assert 0 <= pl["lon"] < 360 and "sign" in pl and "house" in pl
    # Ketu is exactly opposite Rāhu
    assert abs((lords["Ketu"]["lon"] - lords["Rahu"]["lon"]) % 360 - 180.0) < 1e-6
