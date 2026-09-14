#!/usr/bin/env python3
"""
varga.py — Vedic divisional (vārga / aṃśa) charts, pure computation.  [SHIP]

A vārga chart re-maps each body's sidereal longitude to a **divisional sign**: the sign is
divided into *n* equal parts and each part is assigned to a sign by that division's rule. The
D-1 (Rāśi) is the birth chart itself; the D-9 (Navāṃśa) is the most-used divisional. Every
vārga renders on the *same* square chart — only the placements differ (see ephemvis'
``render_vedic_square_svg``).

    varga_sign(lon, 9)        -> the navāṃśa sign index (0 = Aries)
    varga_chart(chart, 9)     -> a chart dict with every body + the Ascendant re-mapped

Rules are a registry keyed by division, so the classical Ṣoḍaśavarga (16 divisions) can be
completed by adding entries. This module ships the everyday set; the rest slot in beside them.
Pure calculation — no interpretation.
"""

from __future__ import annotations

import copy

from . import vedic as _v

# The classical sixteen divisions (Ṣoḍaśavarga). Names for labels/consumers.
VARGA_NAMES = {
    1: "Rāśi", 2: "Horā", 3: "Drekkāṇa", 4: "Chaturthāṃśa", 7: "Saptāṃśa",
    9: "Navāṃśa", 10: "Daśāṃśa", 12: "Dvādaśāṃśa", 16: "Ṣoḍaśāṃśa", 20: "Viṃśāṃśa",
    24: "Chaturviṃśāṃśa", 27: "Bhāṃśa", 30: "Triṃśāṃśa", 40: "Khavedāṃśa",
    45: "Akṣavedāṃśa", 60: "Ṣaṣṭyāṃśa",
}
SHODASHAVARGA = tuple(VARGA_NAMES)          # (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60)


def _equal_part(frac: float, n: int) -> int:
    """The 0-based part index of ``frac`` (degrees into the sign) among ``n`` equal parts."""
    return min(int(frac / (30.0 / n)), n - 1)


# --- per-division rules: (sign_index, frac_deg_into_sign) -> result sign index -------------
# Each returns the divisional sign (0 = Aries). ESSENTIALS are implemented; the remaining
# Ṣoḍaśavarga divisions are added as registry entries in the same shape.

def _d1(s: int, f: float) -> int:
    return s


def _d2(s: int, f: float) -> int:
    # Horā: two 15° halves. Odd (masculine) signs → Leo then Cancer; even signs → the reverse.
    # (Sign index s is even for the odd-numbered signs Aries/Gemini/…) Result is always Leo/Cancer.
    first_half = f < 15.0
    odd_sign = (s % 2 == 0)
    return (4 if first_half else 3) if odd_sign else (3 if first_half else 4)


def _d3(s: int, f: float) -> int:
    # Drekkāṇa: three 10° parts → the sign and its two trines (1st, 5th, 9th from it).
    return (s + _equal_part(f, 3) * 4) % 12


def _d9(s: int, f: float) -> int:
    # Navāṃśa: nine 3°20' parts, counted continuously — equals the classical movable/fixed/dual
    # rule (movable from itself, fixed from the 9th, dual from the 5th).
    return (s * 9 + _equal_part(f, 9)) % 12


def _d10(s: int, f: float) -> int:
    # Daśāṃśa: ten 3° parts. Odd signs count from the sign; even signs from the 9th from it.
    start = s if s % 2 == 0 else (s + 8) % 12
    return (start + _equal_part(f, 10)) % 12


def _d12(s: int, f: float) -> int:
    # Dvādaśāṃśa: twelve 2°30' parts, counted from the sign itself.
    return (s + _equal_part(f, 12)) % 12


# movability of a sign: 0 = movable/cardinal, 1 = fixed, 2 = dual/common (by sign_index % 3);
# element: 0 = fire, 1 = earth, 2 = air, 3 = water (by sign_index % 4).
def _d4(s: int, f: float) -> int:
    # Chaturthāṃśa: four 7°30' parts → the sign and its kendras (1st, 4th, 7th, 10th).
    return (s + _equal_part(f, 4) * 3) % 12


def _d7(s: int, f: float) -> int:
    # Saptāṃśa: seven parts. Odd signs count from the sign; even signs from the 7th from it.
    start = s if s % 2 == 0 else (s + 6) % 12
    return (start + _equal_part(f, 7)) % 12


def _d16(s: int, f: float) -> int:
    # Ṣoḍaśāṃśa: sixteen parts, from Aries / Leo / Sagittarius for movable / fixed / dual signs.
    return ((0, 4, 8)[s % 3] + _equal_part(f, 16)) % 12


def _d20(s: int, f: float) -> int:
    # Viṃśāṃśa: twenty parts, from Aries / Sagittarius / Leo for movable / fixed / dual signs.
    return ((0, 8, 4)[s % 3] + _equal_part(f, 20)) % 12


def _d24(s: int, f: float) -> int:
    # Chaturviṃśāṃśa: twenty-four parts, from Leo for odd signs and Cancer for even signs.
    return ((4 if s % 2 == 0 else 3) + _equal_part(f, 24)) % 12


def _d27(s: int, f: float) -> int:
    # Bhāṃśa: twenty-seven parts, from Aries / Cancer / Libra / Capricorn by the sign's element.
    return ((0, 3, 6, 9)[s % 4] + _equal_part(f, 27)) % 12


# Triṃśāṃśa (D-30): five UNEQUAL segments ruled by Mars/Saturn/Jupiter/Mercury/Venus, mapped to
# a sign of the ruling planet — the order reverses for even signs. (upper_bound_deg, result_sign)
_D30_ODD = ((5, 0), (10, 10), (18, 8), (25, 2), (30, 6))     # Aries, Aquarius, Sag, Gemini, Libra
_D30_EVEN = ((5, 1), (12, 5), (20, 11), (25, 9), (30, 7))    # Taurus, Virgo, Pisces, Cap, Scorpio


def _d30(s: int, f: float) -> int:
    table = _D30_ODD if s % 2 == 0 else _D30_EVEN
    for hi, res in table:
        if f < hi:
            return res
    return table[-1][1]


def _d40(s: int, f: float) -> int:
    # Khavedāṃśa: forty parts, from Aries for odd signs and Libra for even signs.
    return ((0 if s % 2 == 0 else 6) + _equal_part(f, 40)) % 12


def _d45(s: int, f: float) -> int:
    # Akṣavedāṃśa: forty-five parts, from Aries / Leo / Sagittarius for movable / fixed / dual.
    return ((0, 4, 8)[s % 3] + _equal_part(f, 45)) % 12


def _d60(s: int, f: float) -> int:
    # Ṣaṣṭyāṃśa: sixty ½° parts, counted cyclically from the sign itself.
    return (s + _equal_part(f, 60)) % 12


_RULES = {1: _d1, 2: _d2, 3: _d3, 4: _d4, 7: _d7, 9: _d9, 10: _d10, 12: _d12,
          16: _d16, 20: _d20, 24: _d24, 27: _d27, 30: _d30, 40: _d40, 45: _d45, 60: _d60}
IMPLEMENTED = tuple(sorted(_RULES))         # the full Ṣoḍaśavarga
ESSENTIALS = (1, 2, 3, 9, 10, 12)           # the everyday subset


def varga_sign(lon: float, division: int) -> int:
    """The divisional sign index (0 = Aries) of sidereal longitude ``lon`` in the given
    ``division``. Raises ``ValueError`` for a division not yet implemented."""
    fn = _RULES.get(division)
    if fn is None:
        raise ValueError(f"division D-{division} is not a standard vārga; have "
                         f"{', '.join(f'D-{d}' for d in IMPLEMENTED)}")
    lon = float(lon) % 360.0
    return fn(int(lon // 30) % 12, lon % 30.0)


def varga_longitude(lon: float, division: int) -> float:
    """A longitude *within* the divisional sign — the sign start plus the body's position in its
    part, rescaled to the full 30° — so a renderer can show a degree. (Equal-part divisions.)"""
    lon = float(lon) % 360.0
    vs = varga_sign(lon, division)
    if division == 30:                       # unequal segments — carry the raw degree as a placeholder
        return vs * 30.0 + (lon % 30.0)
    part = 30.0 / division
    within = (lon % 30.0) % part
    return vs * 30.0 + (within / part) * 30.0


def varga_chart(chart: dict, division: int) -> dict:
    """Return a copy of ``chart`` with every body and the Ascendant re-mapped to ``division``.

    Longitudes become divisional longitudes and ``sign`` the divisional rāśi; nakṣatra (a D-1
    notion) is dropped. A ``varga`` tag records the division. Expects a **sidereal** chart."""
    out = copy.deepcopy(chart)
    for b in (out.get("bodies") or {}).values():
        if "lon" in b:
            b["lon"] = varga_longitude(b["lon"], division)
            b["sign"] = _v.rashi(b["lon"])
            b.pop("nakshatra", None)
            b.pop("deg_in_sign", None)
    ang = out.get("angles")
    if ang and ang.get("asc") is not None:
        ang["asc"] = varga_longitude(ang["asc"], division)
    out["varga"] = {"division": division, "name": VARGA_NAMES.get(division, f"D-{division}")}
    return out


if __name__ == "__main__":
    demo_lon = 199.47                     # a sidereal Moon in Libra (Tulā), ~19°
    for d in ESSENTIALS:
        print(f"D-{d:<2} {VARGA_NAMES[d]:<12} lon {demo_lon} -> {_v.RASHIS[varga_sign(demo_lon, d)]}")
