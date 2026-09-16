"""openephem — permissive, Swiss-Ephemeris-validated ephemeris & chart engine.

Computes tropical & sidereal charts (planets, Chiron + asteroids, fixed stars,
houses, aspects) validated to arcseconds against Swiss Ephemeris across year
0-2500. Pure calculation core — MIT-licensed, no AGPL dependencies. SVG chart
rendering lives in the companion package **ephemvis** (openephem stays the math).

Quick start:
    from openephem import resolve, assemble
    moment = resolve(date=(1990, 5, 15), time=(14, 30), place="New York, NY")
    chart = assemble(moment)                 # tropical; zodiac="sidereal" for Vedic
    # to draw it:  pip install ephemvis; from ephemvis import render_svg

`assemble()` returns a plain ChartResult dict (see openephem.schema) — the data
contract any renderer or app consumes. Data (DE440, asteroid kernels, Hipparcos)
is fetched at runtime, not shipped.
"""

__version__ = "0.3.0"

from . import (  # noqa: F401 — submodule access (openephem.houses, ...)
    aspects,
    asteroids_skyfield,
    bodies,
    chart,
    decennials,
    derived,
    fetch_kernels,
    firdaria,
    fixed_stars,
    houses,
    hypothetical,
    planets_skyfield,
    profections,
    returns,
    schema,
    service,
    timeplace,
    varga,
    vedic,
    vimshottari,
    zodiacal_releasing,
)
from .aspects import cross_aspects  # noqa: F401 — synastry / cross-chart aspects
from .bodies import available_bodies  # noqa: F401 — the master body list
from .chart import assemble  # noqa: F401
from .timeplace import resolve  # noqa: F401

__all__ = [
    "__version__", "assemble", "resolve", "available_bodies", "cross_aspects",
    "aspects", "houses", "vedic", "timeplace", "chart", "service", "schema",
    "derived", "returns", "bodies", "planets_skyfield", "asteroids_skyfield",
    "hypothetical", "fixed_stars", "fetch_kernels", "profections", "firdaria",
    "zodiacal_releasing", "decennials", "vimshottari", "varga",
]
