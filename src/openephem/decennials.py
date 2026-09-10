#!/usr/bin/env python3
"""
decennials.py — Decennials (Valens time-lords), pure computation.  [SHIP]

The Decennials distribute life among the seven classical planets as chronocrators
("time-lords"). Each planet is allotted its **minor years**; because those minor years
sum to 129, every *general* period — a "decennial" — is a fixed **10 years and 9 months**
(129 months), and seven of them fill ~75¼ years of life before the cycle repeats.

    Minor years:  Saturn 30  Jupiter 12  Mars 15  Sun 19  Venus 8  Mercury 20  Moon 25
                  (Σ = 129 months = 10y 9m per decennial;  7 × = 75y 3m)

Within each decennial the rulership is sub-divided among all seven planets: each sub-period
lasts that planet's minor years reckoned **in months** (Saturn 30 months, … Moon 25 months).
Both the succession of the seven general decennials and the order of the seven sub-periods
follow the **Chaldean order** (Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon), cycling
forward from the starting planet; each decennial's sub-distribution begins with its own
general ruler.

The starting planet (the first "giver of years") is the caller's to choose — the traditional
default is the domicile ruler of the sign holding the **Lot of Fortune**. This module
computes the periods, their rulers, and a dated timeline; it assigns no meaning.
"""

from __future__ import annotations

from . import profections as _p

# minor (lesser) years of the seven classical planets
MINOR_YEARS = {"Saturn": 30, "Jupiter": 12, "Mars": 15, "Sun": 19,
               "Venus": 8, "Mercury": 20, "Moon": 25}
# Chaldean order (descending planetary spheres) — the decennial succession
CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
DECENNIAL_MONTHS = sum(MINOR_YEARS.values())     # 129 = 10 years 9 months
YEAR = 365.2425                # tropical year (consistent with the other time-lords)
MONTH = YEAR / 12.0


def _iso(jd):
    return _p._iso(jd)


def decennials(start_planet: str, jd_birth: float, jd_asof: float | None = None,
               horizon_years: float = 75.25) -> dict:
    """Decennials from ``start_planet`` (a classical planet). Returns the general decennial
    periods (each 10y9m) with their seven planetary sub-periods, and — with ``jd_asof`` —
    the active major/sub lord for that date.

    ``start_planet`` is the first general chronocrator; sub- and major-rulership then pass
    in Chaldean order. Raises ``ValueError`` for a non-classical planet."""
    if start_planet not in MINOR_YEARS:
        raise ValueError(f"start_planet must be one of the seven classical planets "
                         f"({', '.join(CHALDEAN)}), got {start_planet!r}")
    start = CHALDEAN.index(start_planet)
    total_days = horizon_years * YEAR

    timeline = []
    t = jd_birth
    k = 0
    while (t - jd_birth) < total_days - 1e-6 or (jd_asof is not None and t <= jd_asof):
        gen = CHALDEAN[(start + k) % 7]
        major_start = t
        subs = []
        c = major_start
        for j in range(7):
            sub = CHALDEAN[(start + k + j) % 7]
            ln = MINOR_YEARS[sub] * MONTH
            subs.append({"ruler": sub, "start": _iso(c), "end": _iso(c + ln)})
            c += ln
        timeline.append({"ruler": gen, "start": _iso(major_start), "end": _iso(c),
                         "age_start": round((major_start - jd_birth) / YEAR, 2),
                         "age_end": round((c - jd_birth) / YEAR, 2),
                         "subs": subs})       # c = major_start + 129 months
        t = c
        k += 1

    result: dict = {"start": start_planet, "timeline": timeline}
    if jd_asof is not None:
        result["age"] = _p.completed_years(jd_birth, jd_asof)
        asof = result["as_of"] = _iso(jd_asof)
        # locate the active major/sub by ISO-date comparison (all dates share the format)
        for b in timeline:
            if b["start"] <= asof < b["end"]:
                sub = next((s for s in b["subs"] if s["start"] <= asof < s["end"]), b["subs"][-1])
                result["current"] = {"major": b["ruler"], "sub": sub["ruler"],
                                     "major_start": b["start"], "major_end": b["end"],
                                     "sub_start": sub["start"], "sub_end": sub["end"]}
                break
    return result


if __name__ == "__main__":
    r = decennials("Saturn", _p._calendar_to_jd(1970, 9, 14), _p._calendar_to_jd(2026, 6, 1))
    print("start:", r["start"], "| age", r["age"])
    print("current:", {k: r["current"][k] for k in ("major", "sub")})
    print("\ndecennials:")
    for b in r["timeline"]:
        print(f"  age {b['age_start']:>6.2f}-{b['age_end']:<6.2f} {b['start']}..{b['end']}  {b['ruler']}"
              f"  [{' '.join(s['ruler'][:2] for s in b['subs'])}]")
