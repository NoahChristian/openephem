#!/usr/bin/env python3
"""
asteroids_skyfield.py — permissive asteroid engine (Skyfield + JPL SPK).  [SHIP]

Step 3 of the migration. Computes geocentric apparent ecliptic longitude OF DATE
for Chiron + Ceres, Pallas, Juno, Vesta, from per-body JPL SPK (.bsp) kernels.

Licensing: Skyfield is MIT; JPL Horizons SPK kernels are US-Government public
domain (17 U.S.C. sec.105). No AGPL, no CC-BY-SA. Clean to ship.

Getting the kernels (one-time, offline)
---------------------------------------
For each body, generate a small-body SPK from JPL Horizons and drop the .bsp in
--kernel-dir. Browser: https://ssd.jpl.nasa.gov/horizons/app.html
  * Ephemeris Type: "SPK File"
  * Target Body: e.g. "Chiron (2060)", "1 Ceres", "2 Pallas", "3 Juno", "4 Vesta"
  * Time span covering your chart range (e.g. 1550..2650 to match DE440)
  * Download the .bsp; name it as in ASTEROID_TABLE (or pass a custom path).
Chiron note: its orbit is only reliable from ~700 AD onward (chaotic before) —
the same limit swisseph has.

Extensibility: add a body by appending ONE line to ASTEROID_TABLE.

SPK-ID note: JPL's small-body SPK id convention has varied (2000000+num vs
20000000+num). We DON'T rely on a hardcoded id — the engine auto-detects the
target segment in the generated kernel (override per-body if needed).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Asteroid:
    name: str
    number: int             # IAU minor-planet number (for Horizons lookup)
    kernel: str             # expected .bsp filename in --kernel-dir
    spk_id: int | None = None   # optional override; else auto-detected


# One line per body. Extend freely.
ASTEROID_TABLE = [
    Asteroid("Chiron", 2060, "chiron.bsp"),
    Asteroid("Ceres",     1, "ceres.bsp"),
    Asteroid("Pallas",    2, "pallas.bsp"),
    Asteroid("Juno",      3, "juno.bsp"),
    Asteroid("Vesta",     4, "vesta.bsp"),
]
ASTEROIDS = {a.name: a for a in ASTEROID_TABLE}

_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def sign_and_degree(lon: float) -> str:
    lon %= 360.0
    return f"{_SIGNS[int(lon // 30)]} {lon % 30.0:05.2f}"


class SkyfieldAsteroidEngine:
    def __init__(self, planets_ephemeris: str = "de440.bsp", kernel_dir: str = "."):
        import os
        from skyfield.api import load
        self._os = os
        self._load = load
        self._ts = load.timescale()
        self._planets = load(planets_ephemeris)   # provides earth + Sun/SSB chain
        self._earth = self._planets["earth"]
        self._kernel_dir = kernel_dir
        self._targets: dict[str, object] = {}      # name -> resolvable VectorFunction

    # -- kernel loading / target resolution ----------------------------------

    def _resolve_target(self, ast: Asteroid):
        if ast.name in self._targets:
            return self._targets[ast.name]
        path = self._os.path.join(self._kernel_dir, ast.kernel)
        if not self._os.path.exists(path):
            raise FileNotFoundError(
                f"{ast.name}: SPK kernel not found at {path}. Generate it from JPL "
                f"Horizons (Target '{ast.name} ({ast.number})', Ephemeris Type 'SPK File').")
        kernel = self._load(path)

        code = ast.spk_id or self._auto_target_code(kernel)
        # Find the segment for this target to learn its center, then chain so the
        # asteroid is expressed relative to the SSB (matching earth's frame).
        center = self._center_of(kernel, code)
        body = kernel[code]
        if center == 0:                      # already SSB-centered
            target = body
        elif center == 10:                   # Sun-centered -> add SSB->Sun
            target = self._planets["sun"] + body
        else:                                # best effort: add SSB->center
            target = self._planets[center] + body

        self._targets[ast.name] = target
        return target

    @staticmethod
    def _segment_codes(kernel):
        codes = getattr(kernel, "codes", None)
        if codes is None:
            codes = [seg.target for seg in kernel.segments]
        return list(codes)

    def _auto_target_code(self, kernel) -> int:
        # Small-body targets carry large codes (>= 1,000,000). Pick the largest.
        big = [c for c in self._segment_codes(kernel) if c >= 1_000_000]
        if not big:
            raise ValueError("could not auto-detect asteroid target code in kernel; "
                             "set Asteroid.spk_id explicitly")
        return max(big)

    @staticmethod
    def _center_of(kernel, code) -> int:
        for seg in kernel.segments:
            if seg.target == code:
                return seg.center
        return 0

    # -- computations --------------------------------------------------------

    def ecliptic_longitude(self, jd_ut: float, name: str) -> float:
        ast = ASTEROIDS[name]
        target = self._resolve_target(ast)
        t = self._ts.ut1(jd=jd_ut)
        app = self._earth.at(t).observe(target).apparent()
        _lat, lon, _dist = app.ecliptic_latlon(epoch=t)
        return lon.degrees % 360.0

    def available(self) -> list[str]:
        """Names whose kernels are present (so run_parity can skip missing ones)."""
        out = []
        for ast in ASTEROID_TABLE:
            if self._os.path.exists(self._os.path.join(self._kernel_dir, ast.kernel)):
                out.append(ast.name)
        return out


def _demo():
    try:
        eng = SkyfieldAsteroidEngine()
        present = eng.available()
    except (ImportError, FileNotFoundError) as exc:
        print(f"Need skyfield + de440.bsp + asteroid kernels: {exc}")
        return
    if not present:
        print("No asteroid kernels found. Generate chiron.bsp/ceres.bsp/... from Horizons.")
        return
    jd = 2451545.0
    for name in present:
        lon = eng.ecliptic_longitude(jd, name)
        print(f"{name:8} {sign_and_degree(lon):>16}  ({lon:8.4f})")


if __name__ == "__main__":
    _demo()
