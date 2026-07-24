"""schema.py — the ChartResult data contract.

This is the stable boundary between openephem (which *computes* a chart) and any
consumer (ephemvis, a web app, another renderer). `chart.assemble()` returns a
plain dict with this shape; treat it as the public API and version it with the
package. Renderers should depend on this shape, not on openephem internals — so a
chart produced by any engine that emits this shape can be rendered the same way.

All longitudes are ecliptic longitude in degrees [0, 360). `angles` and `cusps`
are `None` for an unknown birth time (houseless chart).

    ChartResult = {
      "zodiac":   "tropical" | "sidereal",
      "ayanamsa": float | None,               # degrees, sidereal only
      "angles":   {"asc": float, "mc": float, "vertex": float,
                   "east_point": float, "coasc": float} | None,  # coasc = Koch co-ascendant
      "cusps":    [float] * 12 | None,         # house cusp longitudes, cusp[0] = 1st
      "bodies":   {name: Body},                # name -> body
      "aspects":  [Aspect],
      "star_aspects": [{"star": name, "body": name, "orb": float}],  # optional; present
                                               #   only when fixed stars were selected
      "warnings": [str],
    }

    Body = {
      "lon":       float,                      # ecliptic longitude, degrees
      "lat":       float,                      # optional, ecliptic latitude
      "retro":     bool,                       # retrograde
      "speed":     float,                      # optional, deg/day
      "sign":      str,   "sign_deg": float,   # optional convenience fields
      "house":     int,                        # optional, 1-12
      "nakshatra": str,   "pada": int,         # optional, sidereal only
    }

    Aspect = {
      "a": name, "b": name,                    # body names (keys of `bodies`)
      "aspect": str,                           # "conjunction" | "opposition" | "square"
                                               #  | "trine" | "sextile" | "quincunx"
                                               #  | "semisextile" | "semisquare"
                                               #  | "sesquiquadrate" | "quintile"
      "angle":  float,                         # exact angle of the aspect (deg)
      "orb":    float,                         # signed orb (deg); +applying / -separating sign varies
      "applying": bool,                        # optional
    }

SCHEMA_VERSION is bumped on any breaking change to this shape (additive fields are
non-breaking). Renderers may check it for compatibility.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

# Aspect names openephem may emit (renderers can map these to glyphs/colours).
ASPECTS = (
    "conjunction", "opposition", "square", "trine", "sextile",
    "quincunx", "semisextile", "semisquare", "sesquiquadrate", "quintile",
)

try:  # typed views are best-effort; the runtime value is always a plain dict
    from typing import TypedDict

    class Body(TypedDict, total=False):
        lon: float
        lat: float
        retro: bool
        speed: float
        sign: str
        sign_deg: float
        house: int
        nakshatra: str
        pada: int

    class Aspect(TypedDict, total=False):
        a: str
        b: str
        aspect: str
        angle: float
        orb: float
        applying: bool

    class Angles(TypedDict, total=False):
        asc: float
        mc: float
        vertex: float
        east_point: float
        coasc: float

    class ChartResult(TypedDict, total=False):
        zodiac: str
        ayanamsa: float | None
        angles: Angles | None
        cusps: list | None
        bodies: dict
        aspects: list
        warnings: list
except Exception:  # pragma: no cover
    Body = Aspect = Angles = ChartResult = dict  # type: ignore


def validate(chart: dict) -> list:
    """Return a list of human-readable problems with `chart` ([] if it looks valid).

    A cheap structural sanity check — not a full schema validator. Useful for
    renderers/tests to fail fast on a malformed dict.
    """
    problems = []
    if not isinstance(chart, dict):
        return ["chart is not a dict"]
    bodies = chart.get("bodies")
    if not isinstance(bodies, dict) or not bodies:
        problems.append("'bodies' must be a non-empty dict")
    else:
        for name, b in bodies.items():
            if not isinstance(b, dict) or "lon" not in b:
                problems.append(f"body {name!r} missing 'lon'")
    cusps = chart.get("cusps")
    if cusps is not None and (not isinstance(cusps, (list, tuple)) or len(cusps) != 12):
        problems.append("'cusps' must be None or a length-12 sequence")
    for a in chart.get("aspects") or []:
        if not {"a", "b", "aspect"} <= set(a):
            problems.append(f"aspect missing a/b/aspect: {a!r}")
    return problems
