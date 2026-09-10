#!/usr/bin/env python3
"""
profections.py — annual / monthly / daily profections (pure computation).  [SHIP]

Profection is a traditional/Hellenistic time-lord technique with a purely mechanical
rule: the Ascendant is the 1st place at age 0, and time advances the "profected"
place by one whole sign per period. Three nested cadences:

    annual   — one whole sign per year of life
    monthly  — the profection year split into 12 equal parts (~30.4 d each),
               advancing one sign per part from the annual sign
    daily    — each monthly part split into 12 (~2.5 d each), advancing one sign
               per part from the monthly sign

For each cadence this module reports the activated whole-sign house, its sign, and
the sign's domicile ruler — the "lord" of that period (Lord of the Year / Month /
Day). It computes ONLY those facts, as plain data. It assigns **no meaning**: no
dignity, condition, sect, or life-topic reading. That interpretive layer is out of
scope for the engine by design (see the README) and belongs to the consuming app.
Domicile rulership below is a fixed astrological correspondence (data).

Profections are whole-sign by construction, independent of the chart's chosen
quadrant house system: each profected place is a 30° sign counted from the rising
sign. A renderer should highlight the profected *sign band*.
"""

from __future__ import annotations

import math

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# Traditional (domicile) rulers — the seven classical planets. Profections are a
# traditional technique, so the lord of a period is the traditional ruler: Mars
# rules Scorpio, Saturn rules Aquarius, Jupiter rules Pisces (not the modern
# outer-planet rulerships). Names match the body keys assemble() emits.
DOMICILE_RULER = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}


# --------------------------------------------------------------------------- #
# Calendar <-> Julian Day (Meeus ch. 7) — self-contained, so this module has no
# intra-package dependency and stays usable standalone.
# --------------------------------------------------------------------------- #

def _calendar_to_jd(year: int, month: int, day: int, hour: float = 12.0) -> float:
    d = day + hour / 24.0
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    if (year, month, day) >= (1582, 10, 15):     # Gregorian reform
        a = y // 100
        b = 2 - a + a // 4
    else:
        b = 0
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


def _jd_to_calendar(jd: float) -> tuple[int, int, int]:
    """Civil (year, month, day) for a Julian Day (Meeus ch. 7, reverse). Handles
    the Julian→Gregorian switch, so it is correct for pre-1582 dates too."""
    jd = jd + 0.5
    z = int(jd)
    f = jd - z
    if z < 2299161:            # before 1582-10-15 → Julian calendar
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = int(b - d - int(30.6001 * e) + f)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return year, month, day


def _iso(jd: float) -> str:
    y, m, d = _jd_to_calendar(jd)
    return f"{y:04d}-{m:02d}-{d:02d}"


def completed_years(jd_birth: float, jd_asof: float) -> int:
    """Whole years of life completed between two moments — i.e. the person's age in
    years, turning on the birthday (calendar convention). Never negative."""
    yb, mb, db = _jd_to_calendar(jd_birth)
    ya, ma, da = _jd_to_calendar(jd_asof)
    age = ya - yb - (1 if (ma, da) < (mb, db) else 0)
    return max(0, age)


def profection_year_bounds(jd_birth: float, jd_asof: float) -> tuple[float, float, int]:
    """(jd of this profection year's birthday, jd of the next birthday, age). The
    profection year runs birthday→birthday; monthly/daily divide that span."""
    yb, mb, db = _jd_to_calendar(jd_birth)
    ya, ma, da = _jd_to_calendar(jd_asof)
    start_year = ya if (ma, da) >= (mb, db) else ya - 1     # most recent birthday
    jd_start = _calendar_to_jd(start_year, mb, db)
    jd_next = _calendar_to_jd(start_year + 1, mb, db)
    return jd_start, jd_next, max(0, start_year - yb)


def _place(asc_index: int, cum: int) -> dict:
    """Profected place `cum` whole signs on from the rising sign."""
    idx = (asc_index + cum) % 12
    sign = SIGNS[idx]
    return {
        "profected_house": (cum % 12) + 1,     # 1..12; 1 = the rising sign
        "profected_sign": sign,
        "profected_sign_index": idx,           # 0=Aries … 11=Pisces
        "profected_sign_lon": idx * 30.0,      # start longitude of the sign band
        "ruler": DOMICILE_RULER[sign],         # lord of this period
    }


def annual_profection(asc_lon: float, age: int) -> dict:
    """Annual profection for a rising longitude (active zodiac, degrees) and integer
    age. `ruler` is the Lord of the Year. Returns a plain dict."""
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    asc_index = int(asc_lon % 360.0 // 30.0)
    return {"method": "annual", "age": age, **_place(asc_index, age % 12)}


def full_profection(asc_lon: float, jd_birth: float, jd_asof: float) -> dict:
    """Annual + monthly + daily profection for a moment `jd_asof` in someone's life.

    Returns the annual place at top level (with `ruler` = Lord of the Year), plus
    `monthly` and `daily` sub-objects (`ruler` = Lord of the Month / Day) each
    carrying its `index` (0-11) and `period_start`/`period_end` ISO dates. The month
    is 1/12 of the birthday→birthday year; the day is 1/12 of the month; both begin
    on the annual/monthly sign and advance one whole sign per part.
    """
    jd_start, jd_next, age = profection_year_bounds(jd_birth, jd_asof)
    year_len = jd_next - jd_start
    t = min(max(jd_asof - jd_start, 0.0), year_len - 1e-9)     # position in the year
    month_len = year_len / 12.0
    mi = min(11, int(t // month_len))
    day_len = month_len / 12.0
    di = min(11, int((t - mi * month_len) // day_len))
    asc_index = int(asc_lon % 360.0 // 30.0)
    step = age % 12

    res = {"method": "annual+monthly+daily", "age": age, **_place(asc_index, step)}
    m_start = jd_start + mi * month_len
    res["monthly"] = {"index": mi, "period_start": _iso(m_start),
                      "period_end": _iso(m_start + month_len),
                      **_place(asc_index, step + mi)}
    d_start = m_start + di * day_len
    res["daily"] = {"index": di, "period_start": _iso(d_start),
                    "period_end": _iso(d_start + day_len),
                    **_place(asc_index, step + mi + di)}
    return res


def profection_for(asc_lon: float, *, age: int | None = None,
                   jd_birth: float | None = None,
                   jd_asof: float | None = None) -> dict:
    """Convenience wrapper. Give `age` for an annual-only result, or a
    (`jd_birth`, `jd_asof`) pair for the full annual+monthly+daily result."""
    if age is not None:
        return annual_profection(asc_lon, age)
    if jd_birth is None or jd_asof is None:
        raise ValueError("pass age=, or both jd_birth= and jd_asof=")
    return full_profection(asc_lon, jd_birth, jd_asof)


if __name__ == "__main__":
    # Virgo rising, born 1990-05-15, as of 2025-01-01 -> age 34, 11th place = Cancer
    # (Lord of the Year: Moon), plus the month/day lords for that date.
    from pprint import pprint
    pprint(full_profection(169.46, _calendar_to_jd(1990, 5, 15),
                           _calendar_to_jd(2025, 1, 1)))
