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
      "profections": Profection | absent,      # optional; present only when a
                                               #   profection age / as-of date was given
      "warnings": [str],
    }

    Profection = {                             # profection — pure data, no meaning
      "method":        "annual" | "annual+monthly+daily",
      "age":           int,                    # whole years of life at the as-of date
      "as_of":         "YYYY-MM-DD",           # present only when derived from a date
      # --- the annual place (top level); its ruler is the Lord of the Year ---
      "profected_house": int,                  # 1-12; 1 = the rising sign (age 0, 12, 24…)
      "profected_sign":  str,                  # the activated whole sign
      "profected_sign_index": int,             # 0=Aries … 11=Pisces
      "profected_sign_lon":   float,           # start longitude of that sign (index*30),
                                               #   active zodiac — anchor for a sign-band highlight
      "ruler":         name,                   # domicile ruler of the profected sign (Lord of the Year)
      "ruler_lon":     float,                  # optional; the lord's natal longitude (positional)
      "ruler_sign":    str,                    # optional; the lord's natal sign (positional)
      "ruler_house":   int,                    # optional; natal house the lord occupies (positional)
      # --- sub-periods (present only with an as-of date); same PeriodBlock shape,
      #     ruler = Lord of the Month / Lord of the Day ---
      "monthly":       PeriodBlock,            # 1/12 of the birthday→birthday year
      "daily":         PeriodBlock,            # 1/12 of the month
    }

    PeriodBlock = {                            # a monthly/daily profection sub-period
      "index":         int,                    # 0-11 within its parent period
      "period_start":  "YYYY-MM-DD",           # inclusive start of this sub-period
      "period_end":    "YYYY-MM-DD",           # start of the next sub-period
      "profected_house": int, "profected_sign": str, "profected_sign_index": int,
      "profected_sign_lon": float, "ruler": name,
      "ruler_lon": float, "ruler_sign": str, "ruler_house": int,   # optional (positional)
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

    class PeriodBlock(TypedDict, total=False):
        index: int
        period_start: str
        period_end: str
        profected_house: int
        profected_sign: str
        profected_sign_index: int
        profected_sign_lon: float
        ruler: str
        ruler_lon: float
        ruler_sign: str
        ruler_house: int

    class Profection(TypedDict, total=False):
        method: str
        age: int
        as_of: str
        profected_house: int
        profected_sign: str
        profected_sign_index: int
        profected_sign_lon: float
        ruler: str
        ruler_lon: float
        ruler_sign: str
        ruler_house: int
        monthly: PeriodBlock
        daily: PeriodBlock

    class ChartResult(TypedDict, total=False):
        zodiac: str
        ayanamsa: float | None
        angles: Angles | None
        cusps: list | None
        bodies: dict
        aspects: list
        profections: Profection
        warnings: list
except Exception:  # pragma: no cover
    Body = Aspect = Angles = Profection = PeriodBlock = ChartResult = dict  # type: ignore


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
