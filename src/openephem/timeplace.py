#!/usr/bin/env python3
"""
timeplace.py - birth date/time/place -> JD(UT).  [SHIP]

Roadmap #3 (the real-world accuracy layer). Converts a local civil birth moment
into the JD(UT) the ephemeris/house engines need, handling the things that
actually dominate chart accuracy:

  * timezone + DST + historical offsets + pre-standard Local Mean Time (LMT),
    via the IANA tz database (public domain) through Python's stdlib `zoneinfo`;
  * coordinate -> timezone lookup, offline, via `timezonefinder` (MIT; bundled
    OSM/ODbL polygon data - attribution required, see references.txt);
  * place -> coordinates via `geopy` (MIT connector), defaulting to free OSM
    Nominatim, with optional Google Maps (`provider='google'`, needs api_key);
  * Julian vs Gregorian calendar for pre-1582 dates;
  * unknown birth time, and ambiguous/nonexistent (DST) local times, as warnings.

Birth-time and timezone errors here dwarf every ephemeris arcsecond - this layer
is where correctness lives.

Deps (all permissive):  pip install tzdata geopy timezonefinder
Attribution obligations: OSM/ODbL (timezonefinder data, Nominatim results);
Google ToS if you use provider='google'. See references.txt.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------- #
# Calendar -> Julian Day (Meeus, ch. 7)
# --------------------------------------------------------------------------- #

def _is_gregorian(year: int, month: int, day: int, calendar: str) -> bool:
    if calendar == "gregorian":
        return True
    if calendar == "julian":
        return False
    return (year, month, day) >= (1582, 10, 15)   # 'auto': Gregorian reform


def julian_day(year: int, month: int, day: int, hour: float = 0.0,
               minute: float = 0.0, second: float = 0.0,
               calendar: str = "auto") -> float:
    """Julian Day for a civil date/time (interpreted in whatever timescale the
    fields are in - pass UT fields to get JD(UT)). Handles Julian/Gregorian."""
    d = day + (hour + minute / 60.0 + second / 3600.0) / 24.0
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    if _is_gregorian(year, month, day, calendar):
        a = y // 100
        b = 2 - a + a // 4
    else:
        b = 0
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


# --------------------------------------------------------------------------- #
# Timezone offset (DST / historical / LMT), with ambiguity + gap detection
# --------------------------------------------------------------------------- #

_FIXED_OFFSET_RE = re.compile(r"^\s*([+-]?)(\d{1,2})(?::?(\d{2}))?\s*$")


def _parse_fixed_offset(tz) -> float | None:
    """Accept a numeric offset (hours) or strings like '+5:30', '-04:00', 'UTC'."""
    if isinstance(tz, (int, float)):
        return float(tz)
    if isinstance(tz, str):
        s = tz.strip()
        if s.upper() in ("UTC", "GMT", "Z"):
            return 0.0
        m = _FIXED_OFFSET_RE.match(s)
        if m and (m.group(1) or m.group(3) is not None):  # avoid matching bare zone digits
            sign = -1.0 if m.group(1) == "-" else 1.0
            hh = int(m.group(2))
            mm = int(m.group(3) or 0)
            return sign * (hh + mm / 60.0)
    return None


def utc_offset_hours(year, month, day, hour, minute, second, tzname, fold=0):
    """Offset (local - UTC, in hours) for a local civil moment in an IANA zone.
    Returns (offset_hours, warnings). Detects DST ambiguity (fold) and gaps."""
    warnings: list[str] = []
    zi = ZoneInfo(tzname)
    base = datetime(year, month, day, hour, minute, int(second))
    dt0 = base.replace(fold=0, tzinfo=zi)
    dt1 = base.replace(fold=1, tzinfo=zi)
    if dt0.utcoffset() != dt1.utcoffset():
        warnings.append(
            f"ambiguous local time (DST fold) - both offsets exist; using fold={fold}")
    chosen = dt1 if fold else dt0
    off = chosen.utcoffset()
    # Gap (nonexistent) detection: round-trip through UTC and back.
    rt = chosen.astimezone(timezone.utc).astimezone(zi)
    if (rt.hour, rt.minute) != (base.hour, base.minute):
        warnings.append(
            "nonexistent local time (DST spring-forward gap) - offset approximated")
    return off.total_seconds() / 3600.0, warnings


# --------------------------------------------------------------------------- #
# Coordinate -> timezone (offline atlas) and place -> coordinate (geocoder)
# --------------------------------------------------------------------------- #

def tz_for_coords(lat: float, lon: float) -> str | None:
    """IANA zone for a coordinate, offline. Requires `timezonefinder`."""
    try:
        from timezonefinder import TimezoneFinder
    except ImportError as exc:
        raise RuntimeError("pip install timezonefinder (or pass tz= explicitly)") from exc
    tf = TimezoneFinder()
    return tf.timezone_at(lat=lat, lng=lon) or tf.certain_timezone_at(lat=lat, lng=lon)


def geocode(query: str, provider: str = "nominatim", api_key: str | None = None,
            user_agent: str = "elpis-astrology", timeout: float = 10.0):
    """Place string -> (lat, lon, resolved_address). Default = free OSM Nominatim
    (1 req/s policy, set a real user_agent). provider='google' needs api_key."""
    try:
        from geopy.geocoders import GoogleV3, Nominatim
    except ImportError as exc:
        raise RuntimeError("pip install geopy (or pass lat=/lon= explicitly)") from exc
    if provider == "google":
        if not api_key:
            raise ValueError("provider='google' requires api_key")
        coder = GoogleV3(api_key=api_key)
    else:
        coder = Nominatim(user_agent=user_agent)
    loc = coder.geocode(query, timeout=timeout)
    if not loc:
        raise ValueError(f"no geocoding result for {query!r}")
    return loc.latitude, loc.longitude, loc.address


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #

@dataclass
class ResolvedMoment:
    jd_ut: float
    lat: float
    lon: float
    tz: str                 # IANA name or fixed-offset string used
    offset_hours: float
    utc_iso: str | None     # readable UTC (modern dates only)
    time_known: bool
    address: str | None
    warnings: list[str] = field(default_factory=list)


def resolve(*, date, time=None, place=None, lat=None, lon=None, tz=None,
            calendar="auto", fold=0, provider="nominatim", api_key=None,
            user_agent="elpis-astrology") -> ResolvedMoment:
    """date=(Y,M,D); time=(H,M[,S]) or None; give place OR lat/lon; tz optional
    (IANA name / fixed offset / None to derive from coords)."""
    warnings: list[str] = []
    year, month, day = date

    # 1) coordinates
    address = None
    if lat is None or lon is None:
        if not place:
            raise ValueError("provide place=... or both lat= and lon=")
        lat, lon, address = geocode(place, provider, api_key, user_agent)

    # 2) timezone
    if tz is None:
        tz = tz_for_coords(lat, lon)
        if not tz:
            raise ValueError("could not determine timezone from coordinates; pass tz=")

    # 3) time (may be unknown)
    if time is None:
        hour, minute, second = 12, 0, 0
        time_known = False
        warnings.append("birth time unknown: assumed 12:00 local (noon). "
                        "Asc/MC/houses are unreliable - treat as houseless.")
    else:
        parts = list(time) + [0, 0, 0]
        hour, minute, second = parts[0], parts[1], parts[2]
        time_known = True

    # 4) UTC offset
    fixed = _parse_fixed_offset(tz)
    if fixed is not None:
        offset = fixed
        tz_label = f"UTC{offset:+g}"
    else:
        offset, w = utc_offset_hours(year, month, day, hour, minute, second, tz, fold)
        warnings += w
        tz_label = tz

    # 5) JD(UT) = JD(local civil) - offset/24  (continuous; calendar-correct)
    jd_local = julian_day(year, month, day, hour, minute, second, calendar)
    jd_ut = jd_local - offset / 24.0

    # readable UTC for modern dates (proleptic-Gregorian datetime is safe there)
    utc_iso = None
    if year >= 1583:
        try:
            local_naive = datetime(year, month, day, hour, minute, int(second))
            utc_dt = local_naive - timedelta(hours=offset)
            utc_iso = utc_dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    return ResolvedMoment(jd_ut=jd_ut, lat=lat, lon=lon, tz=tz_label,
                          offset_hours=offset, utc_iso=utc_iso,
                          time_known=time_known, address=address, warnings=warnings)


if __name__ == "__main__":
    # Offline test (explicit coords, no network): NYC, 1990-05-15 14:30 -> EDT.
    r = resolve(date=(1990, 5, 15), time=(14, 30),
                lat=40.7128, lon=-74.0060)
    print("tz", r.tz, "offset", r.offset_hours, "jd_ut", round(r.jd_ut, 6))
    print("utc", r.utc_iso, "warnings", r.warnings)
    # Unknown-time case
    r2 = resolve(date=(1985, 11, 3), lat=51.5074, lon=-0.1278)
    print("\nunknown-time:", r2.tz, r2.offset_hours, "known?", r2.time_known)
    print("warnings", r2.warnings)
