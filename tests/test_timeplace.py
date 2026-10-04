from openephem import timeplace as tp


def test_julian_day_known():
    assert abs(tp.julian_day(2000, 1, 1, 12, 0, 0) - 2451545.0) < 1e-9
    assert abs(tp.julian_day(1990, 5, 15, 18, 30, 0) - 2448027.270833) < 1e-5


def test_julian_epoch():
    # JD 0.0 = Jan 1, 4713 BC (year -4712) at noon, Julian calendar (definition)
    assert abs(tp.julian_day(-4712, 1, 1, 12, 0, 0, "julian") - 0.0) < 1e-6


def test_calendar_auto_cutover():
    # 'auto' uses Gregorian from 1582-10-15, Julian before
    assert tp.julian_day(1700, 1, 1, 0, 0, 0, "auto") == \
        tp.julian_day(1700, 1, 1, 0, 0, 0, "gregorian")
    assert tp.julian_day(1500, 1, 1, 0, 0, 0, "auto") == \
        tp.julian_day(1500, 1, 1, 0, 0, 0, "julian")


def test_fixed_offset_resolve():
    r = tp.resolve(date=(1990, 5, 15), time=(14, 30), lat=40.0, lon=-75.0, tz=-4.0)
    assert r.time_known
    assert abs(r.offset_hours + 4.0) < 1e-9
    expected = tp.julian_day(1990, 5, 15, 14, 30, 0) + 4.0 / 24.0
    assert abs(r.jd_ut - expected) < 1e-9


def test_string_offset():
    r = tp.resolve(date=(2000, 1, 1), time=(0, 0), lat=0.0, lon=0.0, tz="+05:30")
    assert abs(r.offset_hours - 5.5) < 1e-9


def test_unknown_time():
    r = tp.resolve(date=(1985, 11, 3), lat=51.5, lon=-0.1, tz=0.0)
    assert not r.time_known
    assert any("birth time unknown" in w for w in r.warnings)


# --------------------------------------------------------------------------- #
# Historical civil time: principal-city warnings, dst= override, atlas rules
# --------------------------------------------------------------------------- #
import importlib.util  # noqa: E402
from datetime import date  # noqa: E402

import pytest  # noqa: E402

from openephem import tzatlas  # noqa: E402


def _have_zone(name):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:
        return False


needs_tzdata = pytest.mark.skipif(
    not (_have_zone("America/Chicago") and _have_zone("America/Denver")),
    reason="IANA tzdata not available (pip install tzdata)")

# Synthetic test point: rural central Kansas (round coordinates, not a real birth)
KS_LAT, KS_LON = 38.5, -98.5


@needs_tzdata
def test_pre1967_us_dst_is_flagged():
    # Chicago kept DST in 1955; tzdata extends that to all of America/Chicago.
    r = tp.resolve(date=(1955, 7, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago")
    assert r.offset_hours == -5.0 and r.dst_hours == 1.0
    assert any("pre-1967 US daylight time" in w for w in r.warnings)


@needs_tzdata
def test_dst_false_forces_standard_time():
    r = tp.resolve(date=(1955, 7, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago", dst=False)
    assert r.offset_hours == -6.0 and r.dst_hours == 0.0
    assert r.utc_iso == "1955-07-15T18:00:00+00:00"
    assert not any("pre-1967" in w for w in r.warnings)


@needs_tzdata
def test_dst_true_adds_hour_when_zone_has_none():
    r = tp.resolve(date=(1955, 1, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago", dst=True)
    assert r.offset_hours == -5.0 and r.dst_hours == 1.0


@needs_tzdata
def test_modern_dates_not_flagged():
    r = tp.resolve(date=(1990, 7, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago")
    assert r.offset_hours == -5.0
    assert not any("principal" in w or "pre-19" in w for w in r.warnings)


def test_bad_dst_value():
    with pytest.raises(ValueError):
        tp.resolve(date=(1990, 1, 1), time=(0, 0), lat=0.0, lon=0.0, tz=0.0, dst="no")


KS_STANDARD = tzatlas.AtlasRule(
    name="test: Kansas standard time", start=date(1946, 1, 1),
    end=date(1967, 4, 30), action="standard",
    bbox=(36.99, -102.06, 40.01, -94.58), source="unit-test fixture")


@needs_tzdata
def test_atlas_standard_rule():
    r = tp.resolve(date=(1955, 7, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago", atlas=[KS_STANDARD])
    assert r.offset_hours == -6.0 and r.atlas_rule == KS_STANDARD.name
    assert any("historical atlas rule applied" in w for w in r.warnings)
    # outside the date range -> plain tzdata
    r2 = tp.resolve(date=(1975, 7, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                    tz="America/Chicago", atlas=[KS_STANDARD])
    assert r2.offset_hours == -5.0 and r2.atlas_rule is None


@needs_tzdata
def test_atlas_zone_rule():
    rule = tzatlas.AtlasRule(
        name="test: on Mountain time", start=date(1950, 1, 1), end=date(1960, 1, 1),
        action="zone", zone="America/Denver", polygon=(
            (38.0, -99.0), (39.0, -99.0), (39.0, -98.0), (38.0, -98.0)),
        source="unit-test fixture")
    r = tp.resolve(date=(1955, 1, 15), time=(12, 0), lat=KS_LAT, lon=KS_LON,
                   tz="America/Chicago", atlas=[rule])
    assert r.offset_hours == -7.0 and r.tz == "America/Denver"


def test_atlas_offset_rule_and_fixed_tz_precedence():
    rule = tzatlas.AtlasRule(
        name="test: fixed", start=date(1900, 1, 1), end=date(1950, 1, 1),
        action="offset", offset_hours=-6.5, bbox=(0, -10, 10, 10), source="fixture")
    # a fixed tz is the caller's final answer: atlas is ignored
    r = tp.resolve(date=(1920, 1, 1), time=(0, 0), lat=5.0, lon=0.0, tz=0.0,
                   atlas=[rule])
    assert r.offset_hours == 0.0 and r.atlas_rule is None


# --------------------------------------------------------------------------- #
# Cross-zone cases: city-centre coordinates with synthetic dates/times (not real
# births). Each exercises a different tzdata path through the pre-1970 logic.
# --------------------------------------------------------------------------- #
CITIES = {
    "Flint, MI":        (43.0125, -83.6875, "America/Detroit"),
    "Omaha, NE":        (41.2565, -95.9345, "America/Chicago"),
    "Agate, CO":        (39.4622, -103.9416, "America/Denver"),
    "Seattle, WA":      (47.6062, -122.3321, "America/Los_Angeles"),
    # NW Indiana is on Central time (America/Chicago), unlike the rest of the state.
    "Gary, IN":         (41.5934, -87.3464, "America/Chicago"),
    # Indiana sat on Eastern standard with NO daylight time from 1972 until 2006.
    "Indianapolis, IN": (39.7684, -86.1581, "America/Indiana/Indianapolis"),
    "Bloomington, IN":  (39.1653, -86.5264, "America/Indiana/Indianapolis"),
    # Arizona has observed Mountain standard time year-round (no DST) since 1968.
    "Tempe, AZ":        (33.4255, -111.9400, "America/Phoenix"),
}
PRE_DST = "pre-1967 US daylight time"
PRE_NOTE = "pre-1967 US date"

# (city, date, expected offset, expected dst_hours, expected warning or None)
CROSS_ZONE = [
    # Detroit had no DST in 1955: no DST to strip, but still a principal-city note
    ("Flint, MI", (1955, 7, 15), -5.0, 0.0, PRE_NOTE),
    # 1968: Uniform Time Act in force -> tzdata trusted, no warning
    ("Flint, MI", (1968, 7, 15), -4.0, 1.0, None),
    # 1971: Michigan's statewide exemption is in tzdata (Detroit = whole state)
    ("Flint, MI", (1971, 7, 15), -5.0, 0.0, None),
    # Omaha inherits Chicago's 1955 DST
    ("Omaha, NE", (1955, 7, 15), -5.0, 1.0, PRE_DST),
    # Denver had no DST in 1955, then adopted it 1965-66 ahead of the Act
    ("Agate, CO", (1955, 7, 15), -7.0, 0.0, PRE_NOTE),
    ("Agate, CO", (1966, 7, 15), -6.0, 1.0, PRE_DST),
    # Seattle inherits Los Angeles' (California's) 1955 DST
    ("Seattle, WA", (1955, 7, 15), -7.0, 1.0, PRE_DST),
    # winter: standard time, principal-city note only
    ("Seattle, WA", (1955, 1, 15), -8.0, 0.0, PRE_NOTE),
    # modern dates: plain tzdata, silent
    ("Flint, MI", (1990, 7, 15), -4.0, 1.0, None),
    ("Omaha, NE", (1990, 7, 15), -5.0, 1.0, None),
    ("Agate, CO", (1990, 7, 15), -6.0, 1.0, None),
    ("Seattle, WA", (1990, 7, 15), -7.0, 1.0, None),
    # Gary (NW Indiana) is on Central time -> inherits Chicago's 1955 DST
    ("Gary, IN", (1955, 7, 15), -5.0, 1.0, PRE_DST),
    ("Gary, IN", (1990, 7, 15), -5.0, 1.0, None),
    # Indianapolis on Eastern STANDARD, no DST in 1955 -> principal-city note only
    ("Indianapolis, IN", (1955, 7, 15), -5.0, 0.0, PRE_NOTE),
    # 1990: Indiana's no-DST-on-Eastern era. Offset -5 looks like CDT but is EST and
    # is authoritative post-1970, so it must stay SILENT (not flagged).
    ("Indianapolis, IN", (1990, 7, 15), -5.0, 0.0, None),
    # 2007: after Indiana adopted statewide DST (2006) -> modern EDT, silent
    ("Indianapolis, IN", (2007, 7, 15), -4.0, 1.0, None),
    # Bloomington shares the Indianapolis zone (Monroe Co. follows Indy)
    ("Bloomington, IN", (1955, 7, 15), -5.0, 0.0, PRE_NOTE),
    # Arizona on Mountain standard, no DST in 1955 -> principal-city note only
    ("Tempe, AZ", (1955, 7, 15), -7.0, 0.0, PRE_NOTE),
    # Arizona's permanent MST: authoritative post-1970, stays SILENT
    ("Tempe, AZ", (1990, 7, 15), -7.0, 0.0, None),
]

needs_all_zones = pytest.mark.skipif(
    not all(_have_zone(z) for *_, z in CITIES.values()),
    reason="IANA tzdata not available (pip install tzdata)")


@needs_all_zones
@pytest.mark.parametrize("city,ymd,offset,dst_h,warning", CROSS_ZONE,
                         ids=[f"{c}-{d[0]}-{d[1]:02d}" for c, d, *_ in CROSS_ZONE])
def test_cross_zone_history(city, ymd, offset, dst_h, warning):
    lat, lon, zone = CITIES[city]
    r = tp.resolve(date=ymd, time=(12, 0), lat=lat, lon=lon, tz=zone)
    assert r.tz == zone
    assert r.offset_hours == offset and r.dst_hours == dst_h
    if warning is None:
        assert r.warnings == []
    else:
        assert any(warning in w for w in r.warnings), r.warnings


@needs_all_zones
@pytest.mark.parametrize("city,ymd,offset,dst_h,warning", CROSS_ZONE,
                         ids=[f"{c}-{d[0]}-{d[1]:02d}" for c, d, *_ in CROSS_ZONE])
def test_cross_zone_dst_false_is_standard(city, ymd, offset, dst_h, warning):
    lat, lon, zone = CITIES[city]
    r = tp.resolve(date=ymd, time=(12, 0), lat=lat, lon=lon, tz=zone, dst=False)
    assert r.offset_hours == offset - dst_h and r.dst_hours == 0.0
    # the override is reported only when it actually removed something
    assert any("dst=False" in w for w in r.warnings) == bool(dst_h)
    assert not any("pre-1967" in w for w in r.warnings)


@needs_all_zones
@pytest.mark.skipif(importlib.util.find_spec("timezonefinder") is None,
                    reason="timezonefinder not installed (openephem[geo])")
@pytest.mark.parametrize("city", sorted(CITIES))
def test_coordinate_lookup_picks_expected_zone(city):
    lat, lon, zone = CITIES[city]
    r = tp.resolve(date=(1990, 7, 15), time=(12, 0), lat=lat, lon=lon)
    assert r.tz == zone
