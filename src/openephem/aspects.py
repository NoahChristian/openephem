#!/usr/bin/env python3
"""
aspects.py — aspect detection engine.  [SHIP]

Roadmap #2. Pure longitude math (no ephemeris). Given body longitudes (and
optional daily speeds), finds the aspects between every pair, with configurable
orbs (per-aspect, plus a luminary bonus) and applying/separating classification.

Deterministic and self-contained; unit-testable without any external data.
"""

from __future__ import annotations

from dataclasses import dataclass

# Aspect angle -> default orb (degrees). Majors on by default; minors optional.
MAJOR = {
    "conjunction": (0.0, 8.0),
    "sextile": (60.0, 6.0),
    "square": (90.0, 7.0),
    "trine": (120.0, 8.0),
    "opposition": (180.0, 8.0),
}
MINOR = {
    "semisextile": (30.0, 2.0),
    "semisquare": (45.0, 2.0),
    "quintile": (72.0, 2.0),
    "sesquiquadrate": (135.0, 2.0),
    "quincunx": (150.0, 3.0),
}

LUMINARIES = {"Sun", "Moon"}
LUMINARY_BONUS = 2.0  # extra orb (deg) when a luminary is involved


@dataclass
class Aspect:
    a: str
    b: str
    aspect: str
    angle: float
    orb: float            # signed: separation - exact angle (deg)
    applying: bool | None  # None if speeds not supplied
    exact_sep: float      # actual separation (deg, 0..180)
    chart_a: str | None = None   # source-chart label (cross-chart / synastry aspects)
    chart_b: str | None = None


def _sep(lon1: float, lon2: float) -> float:
    """Angular separation 0..180 degrees."""
    d = abs((lon1 - lon2) % 360.0)
    return 360.0 - d if d > 180.0 else d


def find_aspects(bodies: dict, include_minor: bool = False,
                 orbs: dict | None = None,
                 luminary_bonus: float = LUMINARY_BONUS) -> list[Aspect]:
    """bodies: {name: {"lon": deg, "speed": deg/day (optional)}}.
    Returns the list of aspects found, tightest-orb first."""
    table = dict(MAJOR)
    if include_minor:
        table.update(MINOR)
    if orbs:
        for k, v in orbs.items():
            if k in table:
                table[k] = (table[k][0], float(v))

    names = list(bodies)
    out: list[Aspect] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            na, nb = names[i], names[j]
            la, lb = bodies[na]["lon"], bodies[nb]["lon"]
            sep = _sep(la, lb)
            bonus = luminary_bonus if (na in LUMINARIES or nb in LUMINARIES) else 0.0
            for aspect, (angle, base_orb) in table.items():
                orb = sep - angle
                if abs(orb) <= base_orb + bonus:
                    applying = _applying(bodies.get(na), bodies.get(nb), la, lb, angle)
                    out.append(Aspect(a=na, b=nb, aspect=aspect, angle=angle,
                                      orb=orb, applying=applying, exact_sep=sep))
                    break  # one aspect per pair (nearest by construction of table)
    out.sort(key=lambda x: abs(x.orb))
    return out


def between(bodies_a: dict, bodies_b: dict, include_minor: bool = False,
            orbs: dict | None = None, luminary_bonus: float = LUMINARY_BONUS,
            label_a: str = "A", label_b: str = "B") -> list[Aspect]:
    """Cross-chart (synastry / inter-chart) aspects.

    Every body in `bodies_a` against every body in `bodies_b` (no within-set
    pairs) — synastry, transit-to-natal, progressed-to-natal, etc. Same orb rules
    as find_aspects. Each Aspect keeps the raw names in .a/.b and records the
    source chart in .chart_a/.chart_b, so identical names in both charts (Sun vs
    Sun) stay distinct. Tightest-orb first.

    For transit/progressed 'applying', give the moving chart real speeds and the
    static chart speed 0 (or omit speeds for applying=None)."""
    table = dict(MAJOR)
    if include_minor:
        table.update(MINOR)
    if orbs:
        for k, v in orbs.items():
            if k in table:
                table[k] = (table[k][0], float(v))
    out: list[Aspect] = []
    for na, ba in bodies_a.items():
        la = ba["lon"]
        for nb, bb in bodies_b.items():
            lb = bb["lon"]
            sep = _sep(la, lb)
            bonus = luminary_bonus if (na in LUMINARIES or nb in LUMINARIES) else 0.0
            for aspect, (angle, base_orb) in table.items():
                orb = sep - angle
                if abs(orb) <= base_orb + bonus:
                    out.append(Aspect(a=na, b=nb, aspect=aspect, angle=angle, orb=orb,
                                      applying=_applying(ba, bb, la, lb, angle),
                                      exact_sep=sep, chart_a=label_a, chart_b=label_b))
                    break
    out.sort(key=lambda x: abs(x.orb))
    return out


def cross_aspects(chart_a: dict, chart_b: dict, *, orb: float = 5.0,
                  orbs: dict | None = None, include_minor: bool = False,
                  luminary_bonus: float = 0.0,
                  label_a: str = "inner", label_b: str = "outer") -> list[dict]:
    """Cross-chart (synastry / transit-to-natal) aspects between two chart dicts.

    Pulls ``bodies`` from each ``assemble()``-shaped chart dict and runs every body of
    ``chart_a`` against every body of ``chart_b`` via :func:`between` (no within-chart
    pairs). Unlike :func:`find_aspects`, the default orb is a **flat ``orb`` degrees for
    every aspect** (5° by default) rather than the per-aspect natal table — synastry
    convention; pass ``orbs={aspect: deg}`` to override individual aspects, and
    ``luminary_bonus`` (0 by default here) to widen orbs involving the Sun/Moon.

    Returns a JSON-serialisable list of dicts matching ``assemble()``'s ``aspects``
    shape plus the source-chart labels, tightest-orb first::

        [{"a", "b", "aspect", "angle", "orb", "applying", "chart_a", "chart_b"}, ...]

    ``a``/``chart_a`` name the ``chart_a`` (inner) body, ``b``/``chart_b`` the
    ``chart_b`` (outer) body, so identical names (Sun vs Sun) stay distinct. For
    applying/separating on a transit chart, give the moving chart real speeds and the
    static chart speed 0 (or omit speeds for ``applying=None``)."""
    bodies_a = chart_a.get("bodies") or {}
    bodies_b = chart_b.get("bodies") or {}
    table = dict(MAJOR)
    if include_minor:
        table.update(MINOR)
    flat = {k: float(orb) for k in table}          # flat orb for every active aspect
    if orbs:                                        # per-aspect overrides
        flat.update({k: float(v) for k, v in orbs.items() if k in table})
    found = between(bodies_a, bodies_b, include_minor=include_minor, orbs=flat,
                    luminary_bonus=luminary_bonus, label_a=label_a, label_b=label_b)
    return [{"a": a.a, "b": a.b, "aspect": a.aspect, "angle": a.angle,
             "orb": round(a.orb, 3), "applying": a.applying,
             "chart_a": a.chart_a, "chart_b": a.chart_b} for a in found]


def _applying(ba, bb, la, lb, angle, dt=0.01):
    """Applying if the |orb| is decreasing. Needs both speeds; else None."""
    if not ba or not bb or "speed" not in ba or "speed" not in bb:
        return None
    la2 = la + ba["speed"] * dt
    lb2 = lb + bb["speed"] * dt
    orb_now = abs(_sep(la, lb) - angle)
    orb_next = abs(_sep(la2, lb2) - angle)
    return orb_next < orb_now


if __name__ == "__main__":
    demo = {
        "Sun": {"lon": 10.0, "speed": 1.0},
        "Moon": {"lon": 130.5, "speed": 13.2},
        "Mars": {"lon": 100.2, "speed": 0.5},
        "Saturn": {"lon": 190.4, "speed": -0.05},
    }
    for a in find_aspects(demo):
        app = "applying" if a.applying else ("separating" if a.applying is False else "?")
        print(f"{a.a:7} {a.aspect:12} {a.b:7} orb {a.orb:+.2f} ({app})")
