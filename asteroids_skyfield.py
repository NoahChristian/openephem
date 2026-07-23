#!/usr/bin/env python3
"""
asteroids_skyfield.py — permissive asteroid engine (spiceypy read + Skyfield frame).  [SHIP]

Computes geocentric apparent ecliptic longitude OF DATE for Chiron + Ceres,
Pallas, Juno, Vesta from per-body JPL SPK (.bsp) kernels.

Why spiceypy: JPL Horizons small-body SPK kernels are SPK data **type 21**
(Extended Modified Difference Arrays), which jplephem (Skyfield's native reader)
cannot parse ("SPK data type 21 not yet supported"). spiceypy (CSPICE) reads
type 21 fine, so we use it to get the geocentric apparent state, then hand the
J2000 vector to Skyfield for the of-date ecliptic conversion (matches swisseph to
sub-arcsecond — validated in run_parity).

Licensing: spiceypy is MIT (wraps NASA CSPICE, public domain); Skyfield is MIT;
the SPK kernels are JPL public domain. No AGPL, no copyleft.

Kernels: generate with fetch_kernels.py (Horizons API). Extensibility: add a body
by appending ONE line to ASTEROID_TABLE.
"""

from __future__ import annotations

from dataclasses import dataclass

_AU_KM = 149597870.7
_J2000_JD = 2451545.0
_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


@dataclass(frozen=True)
class Asteroid:
    name: str
    number: int             # IAU minor-planet number (for Horizons lookup)
    kernel: str             # expected .bsp filename in --kernel-dir
    spk_id: int | None = None   # optional override; else auto-detected from kernel


ASTEROID_TABLE = [
    Asteroid("Chiron", 2060, "chiron.bsp"),
    Asteroid("Ceres",     1, "ceres.bsp"),
    Asteroid("Pallas",    2, "pallas.bsp"),
    Asteroid("Juno",      3, "juno.bsp"),
    Asteroid("Vesta",     4, "vesta.bsp"),
]
ASTEROIDS = {a.name: a for a in ASTEROID_TABLE}


def sign_and_degree(lon: float) -> str:
    lon %= 360.0
    return f"{_SIGNS[int(lon // 30)]} {lon % 30.0:05.2f}"


class SkyfieldAsteroidEngine:
    """Read SPK via CSPICE (spiceypy), convert to ecliptic-of-date via Skyfield."""

    def __init__(self, planets_ephemeris: str = "de440.bsp", kernel_dir: str = "."):
        import os
        import spiceypy as sp
        from skyfield.api import load
        self._os = os
        self._sp = sp
        self._ts = load.timescale()
        self._kernel_dir = kernel_dir
        self._loaded: set[str] = set()
        self._target: dict[str, str] = {}

        self._furnsh(planets_ephemeris)          # Earth + Sun for geocentric states

    # -- kernel management ---------------------------------------------------

    def _furnsh(self, path: str):
        if path not in self._loaded:
            self._sp.furnsh(path)
            self._loaded.add(path)

    def _target_for(self, ast: Asteroid) -> str:
        if ast.name in self._target:
            return self._target[ast.name]
        path = self._os.path.join(self._kernel_dir, ast.kernel)
        if not self._os.path.exists(path):
            raise FileNotFoundError(
                f"{ast.name}: SPK kernel not found at {path}. Generate it with "
                f"fetch_kernels.py (Horizons: Target '{ast.name} ({ast.number})').")
        self._furnsh(path)
        tid = str(ast.spk_id) if ast.spk_id else str(list(self._sp.spkobj(path))[0])
        self._target[ast.name] = tid
        return tid

    # -- computation ---------------------------------------------------------

    def ecliptic_longitude(self, jd_ut: float, name: str) -> float:
        import numpy as np
        from skyfield.positionlib import ICRF
        ast = ASTEROIDS[name]
        tid = self._target_for(ast)
        t = self._ts.ut1(jd=jd_ut)
        et = (t.tt - _J2000_JD) * 86400.0          # TDB seconds past J2000 (TT ~ TDB)
        state, _lt = self._sp.spkezr(tid, et, "J2000", "LT+S", "EARTH")  # apparent, km
        pos_au = np.array(state[:3]) / _AU_KM
        p = ICRF(pos_au, t=t, center=399)          # geocentric ICRF position
        _lat, lon, _dist = p.ecliptic_latlon(epoch=t)
        return lon.degrees % 360.0

    def available(self) -> list[str]:
        """Names whose kernels are present (so run_parity can skip missing ones)."""
        return [a.name for a in ASTEROID_TABLE
                if self._os.path.exists(self._os.path.join(self._kernel_dir, a.kernel))]


def _demo():
    try:
        eng = SkyfieldAsteroidEngine(planets_ephemeris="de440s.bsp", kernel_dir="./kernels")
        present = eng.available()
    except (ImportError, FileNotFoundError) as exc:
        print(f"Need spiceypy + skyfield + de440s.bsp + kernels: {exc}")
        return
    for name in present:
        lon = eng.ecliptic_longitude(_J2000_JD, name)
        print(f"{name:8} {sign_and_degree(lon):>16}  ({lon:8.4f})")


if __name__ == "__main__":
    _demo()
