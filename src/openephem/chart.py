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

from . import aspects as _aspects
from . import houses as _houses
from . import vedic as _vedic

_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

DEFAULT_BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "TrueNode", "MeanLilith",
    "Chiron", "Ceres", "Pallas", "Juno", "Vesta",
    "Eros", "Eris", "AsteroidLilith",
]


def _unwrap(d: float) -> float:
    return (d + 540.0) % 360.0 - 180.0


def _house_of(lon: float, cusps) -> int:
    for i in range(12):
        span = (cusps[(i + 1) % 12] - cusps[i]) % 360.0
        if span == 0.0 or (lon - cusps[i]) % 360.0 < span:
            return i + 1
    return 12


def _dispatch_lon(name, jd, planet_eng, asteroid_eng, hypo_eng=None):
    """Ecliptic longitude of an *ephemeris* body (planet/asteroid/hypothetical)."""
    from . import bodies as _B
    b = _B.get(name)
    eng = b.engine if b else None
    if eng == "planet":
        return planet_eng.ecliptic_longitude(jd, name) if planet_eng else None
    if eng == "asteroid":
        return asteroid_eng.ecliptic_longitude(jd, name) if asteroid_eng else None
    if eng == "hypothetical":
        return hypo_eng.ecliptic_longitude(jd, name) if hypo_eng else None
    raise KeyError(f"not an ephemeris body: {name}")


def assemble(resolved, *, house_system="Placidus", bodies=None,
             de440="de440.bsp", kernel_dir="./kernels",
             include_minor_aspects=False, star_orb=1.0,
             zodiac="tropical", ayanamsa="lahiri",
             profection_age=None, profection_as_of=None,
             firdaria_as_of=None, firdaria_horizon=90.0) -> dict:
    from . import bodies as _B
    bodies = bodies or DEFAULT_BODIES
    warnings = list(resolved.warnings)
    jd, lat, lon = resolved.jd_ut, resolved.lat, resolved.lon

    # validate & split the requested bodies by how each is computed
    eph_bodies, point_bodies, lot_bodies, star_bodies = [], [], [], []
    for _name in bodies:
        _b = _B.get(_name)
        if _b is None:
            warnings.append(f"unknown body {_name!r} (see openephem.bodies.available_bodies())")
        elif not _b.implemented:
            warnings.append(f"{_name}: registered but not computed yet ({_b.note})")
        elif _b.engine in ("planet", "asteroid", "hypothetical"):
            eph_bodies.append(_b.name)
        elif _b.engine == "point":
            point_bodies.append(_b.name)
        elif _b.engine == "lot":
            lot_bodies.append(_b.name)
        elif _b.engine == "fixedstar":
            star_bodies.append(_b.name)
        else:
            warnings.append(f"{_name}: engine {_b.engine!r} not wired yet")

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
    hypo_eng = None
    if any((_hb := _B.get(n)) is not None and _hb.engine == "hypothetical" for n in eph_bodies):
        try:
            from . import hypothetical as H
            hypo_eng = H.HypotheticalEngine(de440)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"hypothetical engine unavailable: {exc}")
    star_eng = None
    if star_bodies:  # only load the Hipparcos catalogue if a star was requested
        try:
            from . import fixed_stars as _FS
            star_eng = _FS.SkyfieldFixedStarEngine(de440)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"fixed-star engine unavailable: {exc}")

    # -- bodies (longitude + speed via central difference -> retrograde flag) --
    positions: dict[str, dict] = {}
    for name in eph_bodies:
        try:
            l0 = _dispatch_lon(name, jd, planet_eng, asteroid_eng, hypo_eng)
            if l0 is None:
                continue
            lp = _dispatch_lon(name, jd + 0.5, planet_eng, asteroid_eng, hypo_eng)
            lm = _dispatch_lon(name, jd - 0.5, planet_eng, asteroid_eng, hypo_eng)
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
                      "east_point": h.east_point, "coasc": h.coasc}
            cusps = h.cusps
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"houses ({house_system}): {exc}")
    else:
        warnings.append("houses/angles omitted: birth time unknown")

    # -- aspects --
    abody = {n: ({"lon": p["lon"]} | ({"speed": p["speed"]} if p["speed"] is not None else {}))
             for n, p in positions.items()}
    asp = _aspects.find_aspects(abody, include_minor=include_minor_aspects)

    # -- chart points & lots (added AFTER aspects: shown as bodies, not aspected) --
    def _store(nm, lonv):
        lonv %= 360.0
        positions[nm] = {"lon": lonv, "speed": None, "retro": False,
                         "sign": _SIGNS[int(lonv // 30)], "deg_in_sign": round(lonv % 30.0, 3)}

    for name in point_bodies:
        lonv = None
        if angles and name == "Ascendant":
            lonv = angles["asc"]
        elif angles and name == "Midheaven":
            lonv = angles["mc"]
        elif angles and name == "Vertex":
            lonv = angles.get("vertex")
        elif angles and name == "EastPoint":
            lonv = angles.get("east_point")
        elif angles and name == "CoAscendant":
            lonv = angles.get("coasc")
        elif angles and name == "Descendant":
            lonv = angles["asc"] + 180.0
        elif angles and name == "ImumCoeli":
            lonv = angles["mc"] + 180.0
        elif name == "AriesPoint":
            lonv = 0.0
        elif name == "LibraPoint":
            lonv = 180.0
        elif name == "SouthNode":
            base = (positions.get("TrueNode") or positions.get("MeanNode") or {}).get("lon")
            if base is None and planet_eng:
                try:
                    base = planet_eng.ecliptic_longitude(jd, "TrueNode")
                except Exception:  # noqa: BLE001
                    base = None
            lonv = None if base is None else base + 180.0
        if lonv is None:
            warnings.append(f"{name}: unavailable (needs a known birth time)")
        else:
            _store(name, lonv)

    for name in lot_bodies:
        if name == "PartOfFortune":
            if not (angles and cusps and "Sun" in positions and "Moon" in positions):
                warnings.append("PartOfFortune: needs houses + Sun + Moon selected")
                continue
            asc_l, sun_l = angles["asc"], positions["Sun"]["lon"]
            moon_l = positions["Moon"]["lon"]
            day = _house_of(sun_l, cusps) >= 7          # Sun above the horizon = diurnal
            _store(name, (asc_l + moon_l - sun_l) if day else (asc_l + sun_l - moon_l))
            positions[name]["sect"] = "day" if day else "night"

    if star_bodies:
        from . import fixed_stars as _FS
        _smap = {s.common_name: s for s in _FS.NAMED_STARS}
        for name in star_bodies:
            entry = _smap.get(name)
            if entry is None:
                warnings.append(f"{name}: not in the fixed-star table")
            elif not star_eng:
                warnings.append(f"{name}: fixed-star engine unavailable")
            else:
                try:
                    _store(name, star_eng.ecliptic_longitude(jd, entry))
                    positions[name]["kind"] = "star"
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{name}: {exc}")

    # -- fixed-star conjunction pass (tight orb; stars aren't in the main aspects) --
    star_aspects = []
    if star_bodies:
        _sp = {n: {"lon": positions[n]["lon"]} for n in star_bodies if n in positions}
        _bp = {n: {"lon": positions[n]["lon"]} for n in eph_bodies if n in positions}
        _conj = [_a for _a in _aspects.between(_sp, _bp, orbs={"conjunction": star_orb},
                                               luminary_bonus=0.5) if _a.aspect == "conjunction"]
        _conj.sort(key=lambda a: abs(a.orb))          # Aspect.orb is float -> type-clean
        star_aspects = [{"star": a.a, "body": a.b, "orb": round(a.orb, 3)} for a in _conj]

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
    if star_bodies:
        result["star_aspects"] = star_aspects

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

    # -- profections (pure computation; whole-sign from the Ascendant) --
    # Added last so it uses the active-zodiac (tropical/sidereal) Ascendant. Needs
    # no ephemeris — just the rising sign + a date/age. An as-of date yields the full
    # annual+monthly+daily set (Lord of the Year/Month/Day); an age alone yields the
    # annual place only. Activated house/sign + domicile ruler are returned as data;
    # no interpretation (see profections.py).
    if profection_age is not None or profection_as_of is not None:
        asc_lon = (result.get("angles") or {}).get("asc")
        if asc_lon is None:
            warnings.append("profections omitted: needs a known birth time (Ascendant)")
        else:
            from . import profections as _prof

            def _enrich_lord(block):
                # Attach the period lord's natal placement — positional data, not
                # interpretation — when that planet is among the computed bodies.
                rp = positions.get(block.get("ruler"))
                if rp is not None:
                    block["ruler_lon"] = float(rp["lon"])
                    block["ruler_sign"] = rp.get("sign") or _SIGNS[int(rp["lon"] // 30) % 12]
                    if result.get("cusps"):
                        block["ruler_house"] = _house_of(rp["lon"], result["cusps"])

            jd_birth_local = jd + (resolved.offset_hours or 0.0) / 24.0
            if profection_as_of is not None:
                if isinstance(profection_as_of, (list, tuple)):
                    y, m, d = (list(profection_as_of) + [1, 1])[:3]
                    jd_asof = _prof._calendar_to_jd(int(y), int(m), int(d))
                else:
                    jd_asof = float(profection_as_of)
                prof = _prof.full_profection(asc_lon, jd_birth_local, jd_asof)
                prof["as_of"] = _prof._iso(jd_asof)
                _enrich_lord(prof)
                _enrich_lord(prof["monthly"])
                _enrich_lord(prof["daily"])
            else:
                prof = _prof.annual_profection(asc_lon, profection_age)
                _enrich_lord(prof)
            result["profections"] = prof

    # -- firdaria (Persian time-lords; pure computation; needs sect from the chart) --
    if firdaria_as_of is not None:
        sun_p = positions.get("Sun")
        if sun_p is None or not result.get("cusps"):
            warnings.append("firdaria omitted: needs a known birth time "
                            "(Sun + houses to determine sect)")
        else:
            from . import firdaria as _fir
            from . import profections as _prof
            sect = "day" if _house_of(sun_p["lon"], result["cusps"]) >= 7 else "night"
            jd_birth_local = jd + (resolved.offset_hours or 0.0) / 24.0
            if isinstance(firdaria_as_of, (list, tuple)):
                y, m, d = (list(firdaria_as_of) + [1, 1])[:3]
                jd_asof = _prof._calendar_to_jd(int(y), int(m), int(d))
            else:
                jd_asof = float(firdaria_as_of)
            result["firdaria"] = _fir.firdaria(jd_birth_local, sect, jd_asof,
                                               horizon_years=firdaria_horizon)

    return result


if __name__ == "__main__":
    from . import timeplace as tp
    r = tp.resolve(date=(1990, 5, 15), time=(14, 30), lat=40.7128, lon=-74.0060)
    c = assemble(r)
    print("angles:", c["angles"])
    print("bodies:", list(c["bodies"]))
    print("aspects:", len(c["aspects"]))
    print("warnings:", c["warnings"])
