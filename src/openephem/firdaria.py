#!/usr/bin/env python3
"""
firdaria.py — Persian firdaria (alfridaria) time-lords (pure computation).  [SHIP]

Firdaria divides the life into a fixed 75-year sequence of planetary periods, run in
one of two orders depending on the chart's **sect** (day vs night birth). Each of the
seven planetary periods is sub-divided into seven equal sub-periods, and by default the
two lunar-node periods are sub-divided too (configurable via ``subdivide_nodes``). After
75 years the sequence repeats.

    Planetary years: Sun 10, Venus 8, Mercury 13, Moon 9, Saturn 11, Jupiter 12, Mars 7
    Node years:      North Node 3, South Node 2                       (total = 75)

    Day order:   Sun, Venus, Mercury, Moon, Saturn, Jupiter, Mars, N.Node, S.Node
    Night order: Moon, Saturn, Jupiter, Mars, Sun, Venus, Mercury, N.Node, S.Node

This module computes only the periods and their ruling planet(s) — the active major
lord and sub-lord for a date, plus the full dated timeline — as plain data. It assigns
no meaning; interpretation belongs to the consuming app (see the README).
"""

from __future__ import annotations

from . import (
    profections as _p,  # reuse the calendar helpers (_iso, _calendar_to_jd, _jd_to_calendar)
)

YEAR = 365.2425            # days per firdaria year
TOTAL_YEARS = 75

# (ruler, years) in the two sect orders.
_DAY_ORDER = [("Sun", 10), ("Venus", 8), ("Mercury", 13), ("Moon", 9), ("Saturn", 11),
              ("Jupiter", 12), ("Mars", 7), ("North Node", 3), ("South Node", 2)]
_NIGHT_ORDER = [("Moon", 9), ("Saturn", 11), ("Jupiter", 12), ("Mars", 7), ("Sun", 10),
                ("Venus", 8), ("Mercury", 13), ("North Node", 3), ("South Node", 2)]
# the seven planets in each sect order — the sub-period rotation
_DAY_SUB = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
_NIGHT_SUB = ["Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury"]


def firdaria(jd_birth: float, sect: str, jd_asof: float | None = None,
             horizon_years: float = 90.0, subdivide_nodes: bool = True) -> dict:
    """Firdaria timeline from a birth JD and ``sect`` ('day' or 'night').

    Each planetary period is split into seven equal sub-periods starting with its own
    ruler. With ``subdivide_nodes`` (default), the node periods are also split into
    seven, rotating through the seven planets from the head of the sect order; set it
    False to leave the node periods undivided.

    Returns a dict with ``sect``, the full ``timeline`` (major periods, each with an ISO
    ``start``/``end``, ``age_start``/``age_end``, ``ruler``, and a ``subs`` list), and —
    when ``jd_asof`` is given — a ``current`` block naming the active ``major``/``sub``.
    """
    if sect not in ("day", "night"):
        raise ValueError("sect must be 'day' or 'night'")
    order = _DAY_ORDER if sect == "day" else _NIGHT_ORDER
    subord = _DAY_SUB if sect == "day" else _NIGHT_SUB

    raw = []          # (jd_start, jd_end, ruler, subs[(jd_s, jd_e, ruler)])
    t = jd_birth
    elapsed = 0.0
    while elapsed < horizon_years:
        for ruler, yrs in order:
            start, end = t, t + yrs * YEAR
            subs = []
            if ruler in subord or subdivide_nodes:      # 7 equal sub-periods
                si = subord.index(ruler) if ruler in subord else 0   # node subs start at the head
                sl = yrs / 7.0
                for i in range(7):
                    subs.append((start + i * sl * YEAR, start + (i + 1) * sl * YEAR,
                                 subord[(si + i) % 7]))
            raw.append((start, end, ruler, subs))
            t = end
            elapsed += yrs
            if elapsed >= horizon_years:
                break

    def _fmt(start, end, ruler, subs):
        block = {"ruler": ruler, "start": _p._iso(start), "end": _p._iso(end),
                 "age_start": round((start - jd_birth) / YEAR, 2),
                 "age_end": round((end - jd_birth) / YEAR, 2)}
        if subs:
            block["subs"] = [{"ruler": r, "start": _p._iso(s), "end": _p._iso(e)}
                             for (s, e, r) in subs]
        return block

    result: dict = {"sect": sect, "timeline": [_fmt(*b) for b in raw]}

    if jd_asof is not None:
        result["age"] = _p.completed_years(jd_birth, jd_asof)
        result["as_of"] = _p._iso(jd_asof)
        for start, end, ruler, subs in raw:
            if start <= jd_asof < end:
                cur = {"major": ruler}
                for s, e, r in subs:
                    if s <= jd_asof < e:
                        cur["sub"] = r
                        cur["sub_start"] = _p._iso(s)
                        cur["sub_end"] = _p._iso(e)
                        break
                cur["major_start"] = _p._iso(start)
                cur["major_end"] = _p._iso(end)
                result["current"] = cur
                break
    return result


if __name__ == "__main__":
    jd = _p._calendar_to_jd(1970, 9, 14)
    r = firdaria(jd, "day", _p._calendar_to_jd(2026, 6, 1), horizon_years=80)
    print("sect:", r["sect"], "| age:", r["age"])
    print("current:", r["current"])
    print("\nmajor periods:")
    for b in r["timeline"]:
        print(f"  {b['start']} .. {b['end']}  age {b['age_start']:>5}-{b['age_end']:<5}  {b['ruler']}")
