#!/usr/bin/env python3
"""
chart.py — assemble a full natal chart from a resolved birth moment.  [SHIP]

Orchestrates the whole permissive stack into one serializable chart:
    timeplace (JD/UT) -> planets/asteroids (Skyfield) + houses (analytic) + aspects.

Bodies need Skyfield + DE440 (+ asteroid kernels); if those are unavailable the
chart still returns houses/angles + warnings (graceful degradation), so the API
and renderer work in any environment.
"""

from __future__ import annotations

from . import houses as _houses
from . import aspects as _aspects
from . import vedic as _vedic

_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

DEFAULT_BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "TrueNode", "MeanLilith",
    "Chiron", "Ceres", "Pallas", "Juno", "Vesta",
]


def _unwrap(d: float) -> float:
    return (d + 540.0) % 360.0 - 180.0


def _dispatch_lon(name, jd, planet_eng, asteroid_eng):
    from . import planets_skyfield as P
    from . import asteroids_skyfield as A
    if name in P.PLANET_KEYS or name in P.DERIVED:
        return planet_eng.ecliptic_longitude(jd, name) if planet_eng else None
    if name in A.ASTEROIDS:
        return asteroid_eng.ecliptic_longitude(jd, name) if asteroid_eng else None
    raise KeyError(f"unknown body: {name}")


def assemble(resolved, *, house_system="Placidus", bodies=None,
             de440="de440.bsp", kernel_dir="./kernels",
             include_minor_aspects=False,
             zodiac="tropical", ayanamsa="lahiri") -> dict:
    bodies = bodies or DEFAULT_BODIES
    warnings = list(resolved.warnings)
    jd, lat, lon = resolved.jd_ut, resolved.lat, resolved.lon

    # -- engines (graceful if libs/kernels/DE440 absent) --
    planet_eng = asteroid_eng = None
    try:
        from . import planets_skyfield as P
        planet_eng = P.SkyfieldPlanetEngine(de440)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"planet engine unavailable: {exc}")
    try:
        from . import asteroids_skyfield as A
        asteroid_eng = A.SkyfieldAsteroidEngine(de440, kernel_dir)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"asteroid engine unavailable: {exc}")

    # -- bodies (longitude + speed via central difference -> retrograde flag) --
    positions: dict[str, dict] = {}
    for name in bodies:
        try:
            l0 = _dispatch_lon(name, jd, planet_eng, asteroid_eng)
            if l0 is None:
                continue
            lp = _dispatch_lon(name, jd + 0.5, planet_eng, asteroid_eng)
            lm = _dispatch_lon(name, jd - 0.5, planet_eng, asteroid_eng)
            speed = _unwrap(lp - lm) if (lp is not None and lm is not None) else None
            l0 %= 360.0
            positions[name] = {
                "lon": l0,
                "speed": speed,
                "retro": bool(speed is not None and speed < 0),
                "sign": _SIGNS[int(l0 // 30)],
                "deg_in_sign": round(l0 % 30.0, 3),
            }
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name}: {exc}")

    # -- houses (analytic; only meaningful with a known birth time) --
    angles = cusps = None
    if resolved.time_known:
        try:
            h = _houses.houses_from_jd(jd, lat, lon, house_system)
            angles = {"asc": h.asc, "mc": h.mc, "vertex": h.vertex,
                      "east_point": h.east_point}
            cusps = h.cusps
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"houses ({house_system}): {exc}")
    else:
        warnings.append("houses/angles omitted: birth time unknown")

    # -- aspects --
    abody = {n: ({"lon": p["lon"]} | ({"speed": p["speed"]} if p["speed"] is not None else {}))
             for n, p in positions.items()}
    asp = _aspects.find_aspects(abody, include_minor=include_minor_aspects)

    result = {
        "jd_ut": jd,
        "utc": resolved.utc_iso,
        "lat": lat, "lon": lon, "tz": resolved.tz,
        "offset_hours": resolved.offset_hours,
        "zodiac": "tropical",
        "house_system": house_system if angles else None,
        "angles": angles,
        "cusps": cusps,
        "bodies": positions,
        "aspects": [{"a": a.a, "b": a.b, "aspect": a.aspect, "angle": a.angle,
                     "orb": round(a.orb, 3), "applying": a.applying} for a in asp],
        "warnings": warnings,
    }

    # Sidereal (Vedic): shift every longitude by the ayanamsa. Aspects are
    # separation-based, hence invariant, so they carry over unchanged.
    if zodiac == "sidereal":
        ay = _vedic.ayanamsa(jd, ayanamsa)
        result["zodiac"] = "sidereal"
        result["ayanamsa"] = {"system": ayanamsa, "value": round(ay, 6)}
        for b in positions.values():
            sl = (b["lon"] - ay) % 360.0
            b["lon"] = sl
            b["sign"] = _vedic.rashi(sl)
            b["deg_in_sign"] = round(sl % 30.0, 3)
            ni, nn, pada = _vedic.nakshatra(sl)
            b["nakshatra"] = {"index": ni, "name": nn, "pada": pada}
        if angles:
            result["angles"] = {k: (v - ay) % 360.0 for k, v in angles.items()}
        if cusps:
            result["cusps"] = [(c - ay) % 360.0 for c in cusps]

    return result


if __name__ == "__main__":
    from . import timeplace as tp
    r = tp.resolve(date=(1990, 5, 15), time=(14, 30), lat=40.7128, lon=-74.0060)
    c = assemble(r)
    print("angles:", c["angles"])
    print("bodies:", list(c["bodies"]))
    print("aspects:", len(c["aspects"]))
    print("warnings:", c["warnings"])
