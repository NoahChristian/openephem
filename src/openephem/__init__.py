"""openephem — permissive, Swiss-Ephemeris-validated ephemeris & chart engine.

Computes tropical & sidereal charts (planets, Chiron + asteroids, fixed stars,
houses, aspects) validated to arcseconds against Swiss Ephemeris across year
0-2500, with SVG rendering and an HTTP API. MIT-licensed; no AGPL dependencies.

Quick start:
    from openephem import resolve, assemble, render_svg
    moment = resolve(date=(1990, 5, 15), time=(14, 30), place="New York, NY")
    chart = assemble(moment)                 # tropical; zodiac="sidereal" for Vedic
    svg = render_svg(chart)

Data (DE440, asteroid kernels, Hipparcos) is fetched at runtime, not shipped.
"""

__version__ = "0.1.0"

from . import (                       # noqa: F401 — submodule access (openephem.houses, ...)
    aspects, houses, vedic, timeplace, chart, wheel, service,
    planets_skyfield, asteroids_skyfield, fixed_stars, fetch_kernels,
)
from .chart import assemble           # noqa: F401
from .wheel import render_svg         # noqa: F401
from .timeplace import resolve        # noqa: F401

__all__ = [
    "__version__", "assemble", "render_svg", "resolve",
    "aspects", "houses", "vedic", "timeplace", "chart", "wheel", "service",
    "planets_skyfield", "asteroids_skyfield", "fixed_stars", "fetch_kernels",
]
