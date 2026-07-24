#!/usr/bin/env python3
"""
returns.py — planetary returns (solar, lunar, planetary) by root-finding.

A *return* is the instant a body is again at a given ecliptic longitude: the solar
return (Sun back to its natal longitude, ~yearly), the lunar return (~monthly), the
Saturn return (~29 yr), etc. This is Tier-B / core work — it searches the ephemeris,
which a caller can't do without the positions.

`find_return()` is pure: give it lon_at(jd_ut) -> degrees and a rough jd, and it
finds the crossing NEAREST that jd via Newton on the signed shortest angular
distance. `return_jd()` wires it to an openephem engine; the jd<->datetime helpers
let you build/read the moment. Feed the returned jd back through resolve()/assemble()
(relocated if you want) for the return chart.

Note: a fast, prograde body (Sun/Moon) crosses a longitude once per period — clean.
A slow planet in a retrograde loop can cross the natal degree up to three times near
a return; `find_return` gives the nearest one — call it around each hit to get all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_UNIX_EPOCH_JD = 2440587.5  # JD of 1970-01-01T00:00:00Z
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _signed(lon: float, ref: float) -> float:
    """Shortest signed angular distance lon - ref, in (-180, 180]."""
    return (lon - ref + 180.0) % 360.0 - 180.0


# -- time <-> Julian Date (UT) ----------------------------------------------

def jd_from_datetime(dt: datetime) -> float:
    """Julian Date (UT) from a datetime; naive datetimes are treated as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return _UNIX_EPOCH_JD + (dt - _EPOCH).total_seconds() / 86400.0


def jd(year: int, month: int, day: int, hour: int = 0, minute: int = 0,
       second: float = 0.0) -> float:
    """Julian Date (UT) from a UTC calendar date/time."""
    return jd_from_datetime(datetime(year, month, day, hour, minute,
                                     int(second), int((second % 1) * 1e6),
                                     tzinfo=timezone.utc))


def datetime_from_jd(j: float) -> datetime:
    """UTC datetime from a Julian Date (UT)."""
    return _EPOCH + timedelta(days=j - _UNIX_EPOCH_JD)


# -- the root-finder ---------------------------------------------------------

def find_return(lon_at, target_lon: float, jd_near: float, *,
                mean_motion: float | None = None, tol: float = 1e-6,
                max_iter: int = 60) -> float:
    """jd (UT) of the return nearest `jd_near`.

    lon_at(jd_ut) -> ecliptic longitude in degrees. `mean_motion` (deg/day, signed)
    seeds the search and is used if the local derivative stalls; if omitted it is
    estimated from a one-day sample. `tol` is the convergence orb in degrees.
    """
    if mean_motion is None:
        mean_motion = _signed(lon_at(jd_near + 1.0), lon_at(jd_near))  # deg/day
    if abs(mean_motion) < 1e-9:
        raise ValueError("body is not moving; cannot locate a return")
    # nearest crossing: undo the current signed offset (|offset| <= 180 -> within
    # half a period, so this lands next to the *nearest* return, not a distant one)
    j = jd_near - _signed(lon_at(jd_near), target_lon) / mean_motion
    d = _signed(lon_at(j), target_lon)
    for _ in range(max_iter):
        if abs(d) <= tol:
            return j
        h = 0.02
        v = _signed(lon_at(j + h), lon_at(j - h)) / (2.0 * h)  # local deg/day
        if abs(v) < 1e-6:
            v = mean_motion
        j -= d / v
        d = _signed(lon_at(j), target_lon)
    raise RuntimeError(f"return did not converge (|orb|={abs(d):.2e} deg after "
                       f"{max_iter} iters)")


# -- engine wiring -----------------------------------------------------------

def return_jd(body: str, target_lon: float, jd_near: float, *, engine=None,
              ephemeris_path: str = "de440.bsp", mean_motion: float | None = None,
              tol: float = 1e-6) -> float:
    """Return jd (UT) for `body` back at `target_lon`, nearest `jd_near`.

    Uses openephem's SkyfieldPlanetEngine (Sun/Moon/planets/nodes/liliths). For an
    asteroid, pass a custom lon_at to find_return instead."""
    if engine is None:
        from . import planets_skyfield
        engine = planets_skyfield.SkyfieldPlanetEngine(ephemeris_path)
    return find_return(lambda j: engine.ecliptic_longitude(j, body),
                       target_lon, jd_near, mean_motion=mean_motion, tol=tol)


# mean daily motions (deg/day) as search seeds
_MM = {"Sun": 360.0 / 365.2422, "Moon": 360.0 / 27.32166}


def solar_return(natal_sun_lon: float, jd_near: float, **kw) -> float:
    """jd of the solar return (Sun at its natal longitude) nearest jd_near."""
    return return_jd("Sun", natal_sun_lon, jd_near, mean_motion=_MM["Sun"], **kw)


def lunar_return(natal_moon_lon: float, jd_near: float, **kw) -> float:
    """jd of the lunar return (Moon at its natal longitude) nearest jd_near."""
    return return_jd("Moon", natal_moon_lon, jd_near, mean_motion=_MM["Moon"], **kw)


def planet_return(body: str, natal_lon: float, jd_near: float, **kw) -> float:
    """jd of a planetary return (e.g. Saturn/Jupiter) nearest jd_near."""
    return return_jd(body, natal_lon, jd_near, **kw)
