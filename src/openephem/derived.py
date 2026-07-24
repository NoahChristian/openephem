#!/usr/bin/env python3
"""
derived.py — scope note & recipes: derived / combined charts.

A chart flows through a pipeline:

    A  preprocess   ->   B  openephem core   ->   C  postprocess / display

openephem OWNS stage B. Stages A and C are the caller's; they are documented here
(with the error-prone math provided as helpers) so consumers don't reinvent them.
Most "derived" charts are not new ephemeris math — they live in A or C.

A. PREPROCESSING  (transform the INPUTS, then assemble once)  [caller, before core]
   Change time and/or place, cast one ordinary chart. No new sky math.
   - Davison ............ midpoint instant + great-circle midpoint place, then cast:
                              m = time_midpoint(momentA.utc, momentB.utc)
                              lat, lon = geo_midpoint((latA, lonA), (latB, lonB))
                              davison = assemble(resolve(datetime=m, lat=lat, lon=lon))
   - Relocation ......... same instant, new lat/lon -> resolve()/assemble() again.
   - Secondary progressions ... "a day for a year": assemble at
                          birth_utc + age_years days (still one real sky moment).

B. OPENEPHEM CORE  (needs the ephemeris or the orb engine)  [in scope]
   Facts the caller cannot produce without the positions / aspect math:
   - Positions, houses, angles, in-chart aspects ..... chart.assemble().
   - Synastry / inter-chart aspects ................. DONE: aspects.between(A, B).
   - Returns (solar/lunar/planetary) ................ root-find lon(t)=natal_lon,
                          then assemble that instant. [planned]
   - Timing (transits/ingresses/lunations/eclipses/stations) ... root-finds over
                          positions for when something is exact. [planned]
   - Declination / RA output ........................ a coordinate the core exposes
                          so callers get parallels & precise antiscia. [planned]

C. POSTPROCESSING or DISPLAY  (act on finished ChartResult(s))  [caller / ephemvis, after core]
   No ephemeris — arithmetic, rule-tables, or pixels on what the core returned.
   - Output transforms: composite (midpoint of each longitude), draconic (subtract
        the node), harmonic (lon*N), solar arc, antiscia, Arabic parts/lots,
        midpoint trees.  e.g. {n: {"lon": lon_midpoint(A[n]["lon"], B[n]["lon"])} ...}
   - Technique / time-lord rules: profections, firdaria, zodiacal releasing,
        essential dignities / almuten / sect — deterministic rules over a chart,
        no sky lookup. (A candidate "techniques" layer of its own.)
   - Display: multi-chart overlay (bi-/tri-wheel), the aspect grid — that's ephemvis.

The helpers below cover only the two bits stages A & C most often get wrong
(spherical midpoint of two places; circular midpoint of two longitudes). They are
UTILITIES, not chart builders — the caller still owns the chart composition.
"""

from __future__ import annotations

import math


def lon_midpoint(a: float, b: float, far: bool = False) -> float:
    """Circular midpoint of two ecliptic longitudes (degrees, [0,360)).

    Two midpoints exist, 180 deg apart; the 'near' one (shorter arc) is the
    conventional composite/midpoint. Set far=True for the opposite point."""
    d = (b - a) % 360.0
    if d > 180.0:
        d -= 360.0
    m = (a + d / 2.0) % 360.0
    return (m + 180.0) % 360.0 if far else m


def geo_midpoint(p1, p2):
    """Great-circle midpoint of two (lat, lon) points, in decimal degrees.

    Not the naive average of coordinates — that is wrong across the dateline and
    at high latitude. Returns (lat, lon) with lon in (-180, 180]."""
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlon = lon2 - lon1
    bx = math.cos(lat2) * math.cos(dlon)
    by = math.cos(lat2) * math.sin(dlon)
    lat_m = math.atan2(math.sin(lat1) + math.sin(lat2),
                       math.sqrt((math.cos(lat1) + bx) ** 2 + by ** 2))
    lon_m = lon1 + math.atan2(by, math.cos(lat1) + bx)
    lon_deg = (math.degrees(lon_m) + 540.0) % 360.0 - 180.0
    return (math.degrees(lat_m), lon_deg)


def time_midpoint(dt1, dt2):
    """Midpoint instant between two timezone-aware datetimes (Davison time).

    Both should be UTC / tz-aware; returns a datetime of the same kind. This is
    just the mean instant — no ephemeris involved."""
    return dt1 + (dt2 - dt1) / 2
