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
