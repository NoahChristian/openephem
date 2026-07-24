import os
import pytest
from openephem import returns


def _orb(lon, ref):
    return abs((lon - ref + 180.0) % 360.0 - 180.0)


def test_jd_roundtrip():
    from datetime import datetime, timezone
    j = returns.jd(1990, 5, 15, 14, 30)
    dt = returns.datetime_from_jd(j)
    intended = datetime(1990, 5, 15, 14, 30, tzinfo=timezone.utc)
    # JD's ~2.44e6 magnitude leaves only sub-second float precision — allow < 1s
    assert abs((dt - intended).total_seconds()) < 1.0
    assert abs(returns.jd_from_datetime(dt) - j) < 1e-9


def test_find_return_synthetic_prograde():
    lon_at = lambda j: (j * 1.0) % 360.0            # 1 deg/day
    j = returns.find_return(lon_at, 100.0, jd_near=1000.0)
    assert _orb(lon_at(j), 100.0) < 1e-5
    # nearest crossings to 1000 are 820 and 1180 (both 180 away)
    assert abs(j - 820.0) < 1e-3 or abs(j - 1180.0) < 1e-3


def test_find_return_retrograde():
    lon_at = lambda j: (-2.0 * j) % 360.0           # -2 deg/day
    j = returns.find_return(lon_at, 300.0, jd_near=100.0, mean_motion=-2.0)
    assert _orb(lon_at(j), 300.0) < 1e-5


class _FakeEng:
    """Synthetic engine at the Sun's mean motion — exercises the engine-driven
    return paths offline (no DE440/Skyfield)."""
    def ecliptic_longitude(self, jd, name):
        return (jd * (360.0 / 365.2422)) % 360.0


def test_solar_return_and_return_jd_offline():
    eng = _FakeEng()
    j0 = 2451545.0
    sun0 = eng.ecliptic_longitude(j0, "Sun")
    js = returns.solar_return(sun0, j0 + 365.0, engine=eng)
    assert _orb(eng.ecliptic_longitude(js, "Sun"), sun0) < 1e-3
    jr = returns.return_jd("Sun", sun0, j0 + 365.0, engine=eng)
    assert _orb(eng.ecliptic_longitude(jr, "Sun"), sun0) < 1e-3


@pytest.mark.skipif(not os.path.exists("de440.bsp"), reason="de440.bsp not present")
def test_solar_return_real():
    from openephem import planets_skyfield
    eng = planets_skyfield.SkyfieldPlanetEngine("de440.bsp")
    natal = returns.jd(1990, 5, 15, 14, 30)
    sun0 = eng.ecliptic_longitude(natal, "Sun")
    j = returns.solar_return(sun0, returns.jd(2024, 5, 15), engine=eng)
    assert _orb(eng.ecliptic_longitude(j, "Sun"), sun0) < 1e-5     # Sun is back
    assert abs(j - returns.jd(2024, 5, 15)) < 3.0                  # near the birthday
