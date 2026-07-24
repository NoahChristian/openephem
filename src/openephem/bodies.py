#!/usr/bin/env python3
"""
bodies.py — the master registry of trackable bodies & points.

Single source of truth for "what can I put in a chart." Each entry declares its
`kind` (for display grouping) and its `engine` (how assemble computes it):

    engine="planet"      Sun/Moon/planets/nodes/apogees   -> SkyfieldPlanetEngine
    engine="asteroid"    numbered small bodies/TNOs        -> SkyfieldAsteroidEngine (needs an SPK kernel)
    engine="point"       chart points from angles/geometry -> computed from the houses result
    engine="lot"         Arabic parts                      -> arithmetic on the finished chart (+ sect)
    engine="hypothetical" Uranian/Trans-Pluto/Vulcan/etc.  -> HypotheticalEngine (orbital elements)

`assemble(bodies=[...])` routes each name by its engine and validates against this
registry. `available_bodies()` is the enumerable list a UI selects from. Adding a
body is a registry entry (plus, for asteroids, fetching its kernel); the schema and
renderers don't change — it's just another `bodies` key.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Body:
    name: str
    kind: str                       # luminary|planet|node|apogee|asteroid|tno|point|lot|hypothetical|star
    engine: str                     # planet|asteroid|point|lot|hypothetical|fixedstar
    kernel: str | None = None       # SPK filename (asteroid/tno)
    number: int | None = None       # IAU minor-planet number
    implemented: bool = True        # False = registered but compute not wired yet
    note: str = ""


REGISTRY: dict[str, Body] = {}
ALIASES: dict[str, str] = {}


def _reg(b: Body, *aliases: str) -> Body:
    REGISTRY[b.name] = b
    for a in aliases:
        ALIASES[a.lower()] = b.name
    return b


# -- luminaries & planets (planet engine) ------------------------------------
_reg(Body("Sun", "luminary", "planet"))
_reg(Body("Moon", "luminary", "planet"))
for _n in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"):
    _reg(Body(_n, "planet", "planet"))

# -- lunar nodes & apogees (planet engine, analytic) -------------------------
_reg(Body("TrueNode", "node", "planet"), "NorthNode", "Node", "Rahu")
_reg(Body("MeanNode", "node", "planet"))
_reg(Body("SouthNode", "node", "point", note="opposite the North Node"), "Ketu")
_reg(Body("MeanLilith", "apogee", "planet"), "BlackMoonLilith", "Lilith")
_reg(Body("OscuLilith", "apogee", "planet"), "TrueLilith")

# -- asteroids / TNOs (asteroid engine; each needs an SPK kernel) ------------
_reg(Body("Chiron", "asteroid", "asteroid", kernel="chiron.bsp", number=2060))
_reg(Body("Ceres", "asteroid", "asteroid", kernel="ceres.bsp", number=1))
_reg(Body("Pallas", "asteroid", "asteroid", kernel="pallas.bsp", number=2))
_reg(Body("Juno", "asteroid", "asteroid", kernel="juno.bsp", number=3))
_reg(Body("Vesta", "asteroid", "asteroid", kernel="vesta.bsp", number=4))
_reg(Body("Astraea", "asteroid", "asteroid", kernel="astraea.bsp", number=5))
_reg(Body("Hygeia", "asteroid", "asteroid", kernel="hygeia.bsp", number=10), "Hygiea")
_reg(Body("Eros", "asteroid", "asteroid", kernel="eros.bsp", number=433))
_reg(Body("Eris", "tno", "asteroid", kernel="eris.bsp", number=136199))
_reg(Body("Sedna", "tno", "asteroid", kernel="sedna.bsp", number=90377))
_reg(Body("AsteroidLilith", "asteroid", "asteroid", kernel="lilith_ast.bsp", number=1181),
     "Lilith1181")

# -- chart points (from the houses result / arithmetic) ----------------------
_reg(Body("Ascendant", "point", "point"), "Asc", "AC")
_reg(Body("Midheaven", "point", "point"), "MC", "Medium Coeli")
_reg(Body("Descendant", "point", "point"), "Desc", "DC")
_reg(Body("ImumCoeli", "point", "point"), "IC")
_reg(Body("Vertex", "point", "point"), "Vx")
_reg(Body("EastPoint", "point", "point", note="Equatorial Ascendant"),
     "EquatorialAscendant", "EquatorialArc", "EP")
_reg(Body("AriesPoint", "point", "point", note="0 Aries (tropical)"), "0Aries", "VernalPoint")
_reg(Body("LibraPoint", "point", "point", note="0 Libra (tropical)"), "0Libra")
_reg(Body("CoAscendant", "point", "point", note="Walter Koch co-ascendant"), "CoAsc")
# registered, compute pending (confirm definition — Munkasey polar asc = CoAsc-180?):
_reg(Body("PolarAscendant", "point", "point", implemented=False, note="polar ascendant / 'Polar Arc'"))

# -- lots (arithmetic on the finished chart) ---------------------------------
_reg(Body("PartOfFortune", "lot", "lot", note="Asc+Moon-Sun day / Asc+Sun-Moon night"),
     "Fortune", "PoF", "PartOfFortuna", "Fortuna")

# -- hypothetical bodies (orbital-element engine; hypothetical.py) ------------
# The 8 Uranian ("Hamburg School") planets + Trans-Pluto — propagated from
# published Witte-Sieggrun / Strubell mean elements (facts; rederived, not copied
# from swisseph). Validated < 0.1" vs swisseph across 1935-2024. One engine covers
# all nine.
for _n in ("Cupido", "Hades", "Zeus", "Kronos", "Apollon", "Admetos", "Vulcanus", "Poseidon"):
    _reg(Body(_n, "hypothetical", "hypothetical", note="Uranian (Witte-Sieggrun)"))
_reg(Body("TransPluto", "hypothetical", "hypothetical", note="hypothetical 'Isis' (Strubell 1952)"), "Isis")
_reg(Body("Vulcan", "hypothetical", "hypothetical", note="intra-Mercurial hypothetical (L.H. Weston)"))
_reg(Body("WhiteMoon", "hypothetical", "hypothetical", note="Selena, geocentric mean point"), "Selena")

# -- fixed stars (fixedstar engine; ~30 named stars from Hipparcos J2000 + precession) --
try:
    from . import fixed_stars as _fs
    for _s in _fs.NAMED_STARS:
        _reg(Body(_s.common_name, "star", "fixedstar", note=" ".join(_s.traditions)))
except Exception:  # pragma: no cover — star table optional
    pass


def canonical(name: str) -> str | None:
    """Registry key for a name or alias (case-insensitive); None if unknown."""
    if name in REGISTRY:
        return name
    return ALIASES.get(name.lower())


def get(name: str) -> Body | None:
    key = canonical(name)
    return REGISTRY[key] if key else None


def available_bodies(kind: str | None = None, engine: str | None = None,
                     implemented: bool | None = None) -> list[str]:
    """The master list, optionally filtered by kind/engine/implemented status."""
    out = []
    for b in REGISTRY.values():
        if kind is not None and b.kind != kind:
            continue
        if engine is not None and b.engine != engine:
            continue
        if implemented is not None and b.implemented != implemented:
            continue
        out.append(b.name)
    return out
