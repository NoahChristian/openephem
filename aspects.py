#!/usr/bin/env python3
"""
aspects.py — aspect detection engine.  [SHIP]

Roadmap #2. Pure longitude math (no ephemeris). Given body longitudes (and
optional daily speeds), finds the aspects between every pair, with configurable
orbs (per-aspect, plus a luminary bonus) and applying/separating classification.

Deterministic and self-contained; unit-testable without any external data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
