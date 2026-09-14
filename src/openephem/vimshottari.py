#!/usr/bin/env python3
"""
vimshottari.py — Vimśottarī daśā (Vedic/Jyotiṣa time-lords), pure computation.  [SHIP]

The Vimśottarī daśā divides a nominal **120-year** cycle among the nine grahas
(seven classical planets plus the lunar nodes Rāhu and Ketu). Which daśā a life
opens in, and how much of it remains at birth, is fixed by the **Moon's nakṣatra**:
the 27 nakṣatras cycle the nine daśā-lords three times, so the lord of the Moon's
nakṣatra is the first Mahādaśā, foreshortened to the *balance* left as the Moon
crosses the remainder of that nakṣatra.

    Daśā years:  Ketu 7  Venus 20  Sun 6  Moon 10  Mars 7  Rāhu 18
                 Jupiter 16  Saturn 19  Mercury 17            (Σ = 120)
    Nakṣatra lord = SEQUENCE[nakṣatra_index % 9]   (Aśvinī → Ketu, Bharaṇī → Venus, …)

Each Mahādaśā subdivides into nine **Antardaśās** in the same sequence beginning
with the Mahādaśā lord, each lasting ``maha_years × antar_years / 120``; the same
rule recurses (Pratyantardaśā, …). This module computes the periods, their lords
and a dated timeline; it assigns no meaning.

Input is the Moon's **sidereal** longitude (nakṣatras are sidereal) — the caller
converts from tropical with :mod:`openephem.vedic` (``assemble()`` does this when
given ``vimshottari_as_of=``). Year length defaults to the tropical year used across
openephem's time-lords; pass ``year_length=`` for another daśā convention.
"""

from __future__ import annotations

from . import profections as _p
from . import vedic as _v

# The Vimśottarī sequence and each lord's daśā years (Σ = 120). The sequence order is
# the nakṣatra-lord order: nakṣatra i (0 = Aśvinī) is ruled by SEQUENCE[i % 9].
SEQUENCE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
         "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
TOTAL_YEARS = sum(YEARS.values())          # 120

# Daśā year-length conventions (days). Traditions differ; keep them all available and let the
# caller pick via ``year_length=``. The default is the **solar sidereal** year — the Sun's return
# to a fixed star — which is the usual Jyotiṣa reckoning for the daśā.
SIDEREAL_YEAR = 365.256363                  # solar sidereal (default)
TROPICAL_YEAR = 365.2425                    # what openephem's other time-lords use
JULIAN_YEAR = 365.25                        # some daśā software
SAVANA_YEAR = 360.0                         # 360-day "sāvana" convention
YEAR = SIDEREAL_YEAR                        # module default
_NAK_WIDTH = 360.0 / 27.0                  # 13°20'


def _subdivide(lord_pos: int, start_jd: float, duration_days: float):
    """Split a period (its lord at ``lord_pos`` in SEQUENCE, ``duration_days`` long, opening at
    ``start_jd``) into its nine sub-periods, in sequence from the lord. Yields
    ``(sub_pos, sub_lord, sub_start, sub_end, sub_len_days)``."""
    c = start_jd
    for k in range(9):
        pos = (lord_pos + k) % 9
        length = duration_days * YEARS[SEQUENCE[pos]] / TOTAL_YEARS
        yield pos, SEQUENCE[pos], c, c + length, length
        c += length


def _nested_subs(lord_pos: int, start_jd: float, duration_days: float, depth: int,
                 jd_birth: float):
    """Recursively build ``depth`` levels of sub-periods (Antardaśā, Pratyantardaśā, …), each
    clipped to the life (periods ending before birth dropped, a straddling start clipped to
    birth). Returns a list of ``{ruler, start, end, subs?}`` nodes, or ``None`` at depth 0."""
    if depth <= 0:
        return None
    out = []
    for pos, lord, s, e, length in _subdivide(lord_pos, start_jd, duration_days):
        if e <= jd_birth + 1e-9:
            continue
        node = {"ruler": lord, "start": _p._iso(max(s, jd_birth)), "end": _p._iso(e)}
        deeper = _nested_subs(pos, s, length, depth - 1, jd_birth)
        if deeper:
            node["subs"] = deeper
        out.append(node)
    return out


def vimshottari(moon_lon_sidereal: float, jd_birth: float, jd_asof: float | None = None,
                *, horizon_years: float = 120.0, year_length: float = YEAR,
                levels: int = 3) -> dict:
    """Vimśottarī daśā for a Moon at ``moon_lon_sidereal`` (sidereal degrees).

    Returns the Mahādaśā periods (each recursively sub-divided ``levels`` deep — 3 gives
    Mahā → Antar → Pratyantardaśā), the birth nakṣatra and daśā balance, and — with
    ``jd_asof`` — the active Mahā/Antar/Pratyantar lords for that date. The first Mahādaśā is
    clipped to the balance remaining at birth (age 0); subsequent Mahādaśās are whole.
    ``horizon_years`` bounds how far the timeline runs (one full cycle is 120 years);
    ``year_length`` selects the daśā year convention (default solar sidereal)."""
    lon = float(moon_lon_sidereal) % 360.0    # plain float (Moon lon may arrive as numpy)
    nak_idx = int(lon // _NAK_WIDTH)
    pada = int((lon - nak_idx * _NAK_WIDTH) // (_NAK_WIDTH / 4.0)) + 1
    lord0_pos = nak_idx % 9
    lord0 = SEQUENCE[lord0_pos]
    elapsed = (lon - nak_idx * _NAK_WIDTH) / _NAK_WIDTH       # fraction of the nakṣatra elapsed
    Y = year_length

    # the first Mahādaśā conceptually began before birth; birth sits `elapsed` of the way in
    concept_start = jd_birth - YEARS[lord0] * elapsed * Y
    balance_years = YEARS[lord0] * (1.0 - elapsed)

    timeline = []
    t = concept_start
    m = 0
    while m < 60:
        lord_pos = (lord0_pos + m) % 9
        lord = SEQUENCE[lord_pos]
        m_len = YEARS[lord] * Y
        m_start, m_end = t, t + m_len
        past_horizon = (m_start - jd_birth) >= horizon_years * Y
        if past_horizon and (jd_asof is None or m_start > jd_asof):
            break
        if m_end > jd_birth + 1e-9:                          # skip a fully pre-birth period
            vis_start = max(m_start, jd_birth)
            subs = _nested_subs(lord_pos, m_start, m_len, levels - 1, jd_birth) or []
            timeline.append({"ruler": lord, "start": _p._iso(vis_start), "end": _p._iso(m_end),
                             "age_start": round((vis_start - jd_birth) / Y, 2),
                             "age_end": round((m_end - jd_birth) / Y, 2), "subs": subs})
        t = m_end
        m += 1

    result: dict = {
        "system": "vimshottari",
        "moon_nakshatra": {"index": nak_idx, "name": _v.NAKSHATRAS[nak_idx],
                           "pada": pada, "lord": lord0},
        "balance": {"lord": lord0, "years": round(balance_years, 3)},
        "timeline": timeline,
    }
    if jd_asof is not None:
        result["age"] = _p.completed_years(jd_birth, jd_asof)
        result["as_of"] = _p._iso(jd_asof)
        # walk Mahā → Antar → Pratyantar by nested subdivision at the as-of date
        cur = _current(lord0_pos, concept_start, jd_asof, Y)
        if cur:
            result["current"] = cur
    return result


def _current(lord0_pos: int, concept_start: float, jd_asof: float, Y: float) -> dict:
    """Locate the active Mahā/Antar/Pratyantar lords (and their spans) at ``jd_asof``."""
    # find the Mahādaśā containing jd_asof
    t = concept_start
    for m in range(60):
        lord_pos = (lord0_pos + m) % 9
        m_len = YEARS[SEQUENCE[lord_pos]] * Y
        if t <= jd_asof < t + m_len or (m == 59):
            maha_pos, maha_start, maha_len = lord_pos, t, m_len
            break
        t += m_len
    else:  # pragma: no cover
        return {}
    # antardaśā within the Mahādaśā
    antar = next((x for x in _subdivide(maha_pos, maha_start, maha_len)
                  if x[2] <= jd_asof < x[3]), None)
    if antar is None:
        return {}
    a_pos, a_lord, a_start, a_end, a_len = antar
    # pratyantardaśā within the antardaśā
    praty = next((x for x in _subdivide(a_pos, a_start, a_len)
                  if x[2] <= jd_asof < x[3]), None)
    out = {"maha": SEQUENCE[maha_pos], "antar": a_lord,
           "maha_start": _p._iso(maha_start), "maha_end": _p._iso(maha_start + maha_len),
           "antar_start": _p._iso(a_start), "antar_end": _p._iso(a_end)}
    if praty is not None:
        out["pratyantar"] = praty[1]
        out["pratyantar_start"] = _p._iso(praty[2])
        out["pratyantar_end"] = _p._iso(praty[3])
    return out


if __name__ == "__main__":
    # a Moon at sidereal 45° (in Rohiṇī, ruled by the Moon) — demo, no exemplar data
    jd_b = _p._calendar_to_jd(2000, 1, 1)
    r = vimshottari(45.0, jd_b, _p._calendar_to_jd(2040, 6, 1))
    print("nakshatra:", r["moon_nakshatra"], "| balance:", r["balance"], "| age", r["age"])
    print("current:", {k: r["current"][k] for k in ("maha", "antar", "pratyantar")})
    print("\nmahadashas:")
    for b in r["timeline"]:
        print(f"  age {b['age_start']:>6.2f}-{b['age_end']:<6.2f} {b['ruler']:8}"
              f"  [{' '.join(s['ruler'][:2] for s in b['subs'])}]")
