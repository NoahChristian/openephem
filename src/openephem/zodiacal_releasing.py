#!/usr/bin/env python3
"""
zodiacal_releasing.py — Zodiacal Releasing (Valens) time-lords (pure computation).  [SHIP]

Zodiacal Releasing (ZR) releases time-periods from a Lot — usually the Lot of Spirit
(action/career) or the Lot of Fortune (body/circumstance). Starting from the Lot's sign,
periods are released in zodiacal order; each sign's period length is its ruler's Lesser
Years (in years at level 1). Sub-periods (levels 2–4) repeat the same numbers with the
unit divided by twelve each level (years → months → ⅟12-month → …), cascading around the
zodiac to fill the parent period.

    Lesser Years by sign:  Ari 15  Tau 8  Gem 20  Cnc 25  Leo 19  Vir 20
                           Lib 8   Sco 15 Sag 12  Cap 27  Aqu 30  Pis 12   (Σ = 211)

Two features of the technique are marked as data (not interpreted):
  * **Loosing of the Bond (LB):** when a level's sub-periods complete a full circuit of
    the zodiac and the parent period still has time left, the chain "looses" and leaps to
    the sign opposite the level's origin, continuing from there.
  * **Peak periods:** sub-periods whose sign is angular (1st/10th/7th/4th) from the Lot.

This module computes the periods, their signs, and those flags. It assigns no meaning.
The exact LB / peak conventions vary between authors — see the module tests and README.
"""

from __future__ import annotations

from . import profections as _p

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
LESSER_YEARS = [15, 8, 20, 25, 19, 20, 8, 15, 12, 27, 30, 12]   # by sign index
YEAR = 365.2425                # tropical year (consistent with profections / firdaria)
_TOTAL = sum(LESSER_YEARS)      # 211


LOT_NAMES = ("fortune", "spirit", "eros", "necessity", "courage", "victory", "nemesis")


def hermetic_lots(sect: str, asc: float, sun: float, moon: float, mercury: float,
                  venus: float, mars: float, jupiter: float, saturn: float) -> dict:
    """The seven Hermetic Lots (ecliptic longitudes), sect-aware. Fortune and Spirit are
    the primaries; the other five are built from them (Eros/Victory from Spirit,
    Necessity/Courage/Nemesis from Fortune)."""
    day = sect == "day"

    def L(a, b):                      # Asc + (a - b) by day, Asc + (b - a) by night
        return (asc + (a - b) if day else asc + (b - a)) % 360.0

    fortune, spirit = L(moon, sun), L(sun, moon)
    return {
        "fortune": fortune, "spirit": spirit,
        "eros": L(venus, spirit), "necessity": L(fortune, mercury),
        "courage": L(fortune, mars), "victory": L(spirit, jupiter),
        "nemesis": L(fortune, saturn),
    }


def lot(kind: str, sect: str, asc: float, sun: float, moon: float) -> float:
    """Convenience: the Lot of Fortune or Spirit only (the rest need the other bodies —
    use :func:`hermetic_lots`)."""
    if kind not in ("fortune", "spirit"):
        raise ValueError("use hermetic_lots() for lots other than fortune/spirit")
    day = sect == "day"
    if kind == "fortune":
        return (asc + (moon - sun) if day else asc + (sun - moon)) % 360.0
    return (asc + (sun - moon) if day else asc + (moon - sun)) % 360.0


def _release(start_idx: int, total_days: float, unit_days: float):
    """Release periods from `start_idx` filling `total_days`; each sign = LesserYears*unit.
    Returns [(sign_idx, length_days, is_lb_entry)] with the Loosing of the Bond applied."""
    out = []
    sign = start_idx
    filled = 0.0
    n = 0
    lb_next = False
    while filled < total_days - 1e-6:
        length = LESSER_YEARS[sign] * unit_days
        remaining = total_days - filled
        out.append((sign, min(length, remaining), lb_next))
        filled += min(length, remaining)
        n += 1
        lb_next = False
        if n % 12 == 0:                      # full circuit done -> loose the bond
            sign = (start_idx + 6) % 12
            lb_next = True
        else:
            sign = (sign + 1) % 12
    return out


def _iso(jd):
    return _p._iso(jd)


def releasing(lot_lon: float, jd_birth: float, jd_asof: float | None = None,
              horizon_years: float = 100.0, lot_name: str = "fortune",
              fortune_lon: float | None = None) -> dict:
    """Zodiacal Releasing from a Lot longitude. Returns L1 periods (each with nested L2),
    peak/LB flags, and — with `jd_asof` — the active L1→L4 sign path.

    Peak periods are the signs angular (1st/4th/7th/10th) from the **Lot of Fortune**
    (pass `fortune_lon`); when it is omitted they are reckoned from the released Lot."""
    lot_idx = int(lot_lon // 30) % 12
    peak_ref = int((fortune_lon if fortune_lon is not None else lot_lon) // 30) % 12
    angles = {(peak_ref + k) % 12 for k in (0, 3, 6, 9)}

    def peak(sign):
        return sign in angles

    l1_raw = _release(lot_idx, horizon_years * YEAR, YEAR)
    timeline = []
    t = jd_birth
    for s1, len1, lb1 in l1_raw:
        start1, end1 = t, t + len1
        l2 = []
        c = start1
        for s2, len2, lb2 in _release(s1, len1, YEAR / 12.0):
            l2.append({"sign": SIGNS[s2], "sign_index": s2, "start": _iso(c),
                       "end": _iso(c + len2), "peak": peak(s2), "lb": lb2})
            c += len2
        timeline.append({"sign": SIGNS[s1], "sign_index": s1,
                         "start": _iso(start1), "end": _iso(end1),
                         "age_start": round((start1 - jd_birth) / YEAR, 2),
                         "age_end": round((end1 - jd_birth) / YEAR, 2),
                         "peak": peak(s1), "lb": lb1, "l2": l2})
        t = end1

    result: dict = {"lot": lot_name, "lot_sign": SIGNS[lot_idx], "lot_lon": round(lot_lon, 4),
                    "peak_from": SIGNS[peak_ref], "timeline": timeline}

    if jd_asof is not None:
        result["age"] = _p.completed_years(jd_birth, jd_asof)
        result["as_of"] = _iso(jd_asof)
        # drill the active path L1 -> L4
        path = {}
        # L1
        t = jd_birth
        cur1 = None
        for s1, len1, _ in l1_raw:
            if t <= jd_asof < t + len1:
                cur1 = (s1, t, t + len1)
                break
            t += len1
        if cur1:
            s1, a, b = cur1
            path["l1"] = {"sign": SIGNS[s1], "start": _iso(a), "end": _iso(b), "peak": peak(s1)}
            # descend levels 2..4
            parent_sign, parent_start, parent_len, unit = s1, a, b - a, YEAR / 12.0
            for lvl in ("l2", "l3", "l4"):
                c = parent_start
                for s, ln, lb in _release(parent_sign, parent_len, unit):
                    if c <= jd_asof < c + ln:
                        path[lvl] = {"sign": SIGNS[s], "start": _iso(c), "end": _iso(c + ln),
                                     "peak": peak(s), "lb": lb}
                        parent_sign, parent_start, parent_len = s, c, ln
                        unit /= 12.0
                        break
                    c += ln
        result["current"] = path
    return result


if __name__ == "__main__":
    # exemplar: night chart, Asc Leo 15, Sun 171.08 Virgo, Moon 334.91 Pisces
    lp = lot("spirit", "night", 135.0, 171.08, 334.91)
    r = releasing(lp, _p._calendar_to_jd(1970, 9, 14), _p._calendar_to_jd(2026, 6, 1), horizon_years=90)
    print("Lot of Spirit:", r["lot_sign"], round(lp, 2), "| age", r["age"])
    print("current:", {k: v["sign"] for k, v in r["current"].items()})
    print("\nL1 periods:")
    for b in r["timeline"]:
        if b["age_start"] < 90:
            tag = " PEAK" if b["peak"] else ""
            print(f"  age {b['age_start']:>6.2f}-{b['age_end']:<6.2f} {b['start']}..{b['end']}  {b['sign']}{tag}")
