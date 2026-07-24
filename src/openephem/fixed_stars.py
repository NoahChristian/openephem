#!/usr/bin/env python3
"""
fixed_stars.py — permissive fixed-star module for the ephemeris migration.

Fixed stars (Regulus, Sirius, Algol, ...) are NOT solar-system bodies, so they
need no ephemeris integration and no SPK/asteroid data. Their chart position is:

    catalog ICRS/J2000 (RA/Dec + proper motion)
        -> apply proper motion + parallax + aberration
        -> precess/nutate to the equinox OF THE DATE
        -> convert equatorial -> ecliptic
        -> ecliptic longitude (what astrologers read, e.g. "Regulus 0 Virgo")

Everything here is permissive:
  * Skyfield (MIT) does the astrometry and precession.
  * Star coordinates are astronomical FACTS (not copyrightable). Default path
    pulls them from the Hipparcos catalog (ESA, free with acknowledgment) by HIP
    number; for a zero-external-data commercial build, freeze coordinates into
    the INLINE_COORDS overrides below (a VizieR one-liner is given) so nothing
    but facts ships.

This module is useful standalone (the NAMED_STARS table + engine) and is also
consumed by generate_oracle.py to validate the Skyfield longitudes against a
swisseph `swe_fixstar` authority column.

    pip install skyfield          # MIT — safe to SHIP (unlike pyswisseph)
    python fixed_stars.py         # demo: prints Regulus/Sirius/Algol, shows precession
"""

from __future__ import annotations

from dataclasses import dataclass

J2000_JD = 2451545.0  # TT Julian date of the J2000.0 epoch


# --------------------------------------------------------------------------- #
# Named-star table (facts: name -> HIP + tradition tags).
#
# Coordinates are intentionally NOT hardcoded here by default — the engine pulls
# authoritative J2000 astrometry from Hipparcos by HIP number, which keeps this
# table small and correct. To ship with zero external data, fill INLINE_COORDS
# (below) with J2000 ICRS values, e.g. from VizieR:
#   https://vizier.cds.unistra.fr/viz-bin/VizieR-3?-source=I/239/hip_main&HIP==49669
# and set FixedStar.use_inline=True per star (or globally in the engine).
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class FixedStar:
    common_name: str
    hip: int
    swe_name: str                    # name swisseph's sefstars.txt matches on
    traditions: tuple[str, ...] = () # e.g. "behenian", "royal"


# Curated set: the 15 Behenian stars + the 4 Royal Stars (Watchers) + the most
# commonly used named stars in practice. Extend freely — any bright star has a HIP.
NAMED_STARS: list[FixedStar] = [
    # --- Behenian fixed stars (medieval magical/astrological canon) ---
    FixedStar("Algol",        14576, "Algol",        ("behenian",)),
    FixedStar("Alcyone",      17702, "Alcyone",      ("behenian", "pleiades")),
    FixedStar("Aldebaran",    21421, "Aldebaran",    ("behenian", "royal")),
    FixedStar("Capella",      24608, "Capella",      ("behenian",)),
    FixedStar("Sirius",       32349, "Sirius",       ("behenian",)),
    FixedStar("Procyon",      37279, "Procyon",      ("behenian",)),
    FixedStar("Regulus",      49669, "Regulus",      ("behenian", "royal")),
    FixedStar("Gienah",       59803, "Gienah",       ("behenian",)),   # gamma Corvi
    FixedStar("Spica",        65474, "Spica",        ("behenian",)),
    FixedStar("Arcturus",     69673, "Arcturus",     ("behenian",)),
    FixedStar("Alphecca",     76267, "Alphecca",     ("behenian",)),
    FixedStar("Antares",      80763, "Antares",      ("behenian", "royal")),
    FixedStar("Vega",         91262, "Vega",         ("behenian",)),
    FixedStar("Deneb Algedi", 107556, "Deneb Algedi", ("behenian",)), # delta Cap
    FixedStar("Fomalhaut",    113368, "Fomalhaut",   ("behenian", "royal")),

    # --- other commonly-used named stars ---
    FixedStar("Rigel",        24436, "Rigel"),
    FixedStar("Bellatrix",    25336, "Bellatrix"),
    FixedStar("Betelgeuse",   27989, "Betelgeuse"),
    FixedStar("Castor",       36850, "Castor"),
    FixedStar("Pollux",       37826, "Pollux"),
    FixedStar("Denebola",     57632, "Denebola"),
    FixedStar("Alphard",      46390, "Alphard"),
    FixedStar("Zubenelgenubi", 72622, "Zuben Elgenubi"),  # alpha Lib
    FixedStar("Zubeneschamali", 74785, "Zuben Eschamali"), # beta Lib
    FixedStar("Altair",       97649, "Altair"),
    FixedStar("Deneb",        102098, "Deneb"),           # alpha Cyg
    FixedStar("Achernar",     7588,  "Achernar"),
    FixedStar("Canopus",      30438, "Canopus"),
    FixedStar("Alpheratz",    677,   "Alpheratz"),
    FixedStar("Hamal",        9884,  "Hamal"),
    FixedStar("Markab",       113963, "Markab"),
    FixedStar("Scheat",       113881, "Scheat"),
]

# Optional: freeze J2000 ICRS coordinates here to ship WITHOUT the Hipparcos file.
# key = HIP number, value = dict(ra_deg, dec_deg, pm_ra_masyr, pm_dec_masyr, parallax_mas).
# Leave empty to pull from Hipparcos by HIP (default).
INLINE_COORDS: dict[int, dict] = {
    # 49669: dict(ra_deg=152.092962, dec_deg=11.967206,
    #             pm_ra_masyr=-249.40, pm_dec_masyr=4.91, parallax_mas=41.13),  # Regulus (example)
}


# --------------------------------------------------------------------------- #
# Permissive Skyfield engine (MIT) — the production candidate.
# --------------------------------------------------------------------------- #

class SkyfieldFixedStarEngine:
    """Compute geocentric apparent ecliptic longitude (of date) for fixed stars,
    plus altaz for paran work. Uses Skyfield (MIT) + public star astrometry."""

    def __init__(self, ephemeris_path: str = "de421.bsp",
                 prefer_inline: bool = False):
        # Lazy imports so the NAMED_STARS table is usable without skyfield.
        from skyfield.api import Star, load
        self._Star = Star
        self._load = load
        self._ts = load.timescale()
        self._eph = load(ephemeris_path)
        self._earth = self._eph["earth"]
        self._prefer_inline = prefer_inline
        self._hip_df = None          # loaded on demand
        self._star_cache: dict[int, object] = {}

    # -- star construction ---------------------------------------------------

    def _hipparcos(self):
        if self._hip_df is None:
            from skyfield.data import hipparcos
            with self._load.open(hipparcos.URL) as f:
                self._hip_df = hipparcos.load_dataframe(f)
        return self._hip_df

    def _star_object(self, entry: FixedStar):
        if entry.hip in self._star_cache:
            return self._star_cache[entry.hip]

        inline = INLINE_COORDS.get(entry.hip)
        if inline and (self._prefer_inline or True):
            # J2000 ICRS facts frozen in-repo -> zero external data dependency.
            star = self._Star(
                ra_hours=inline["ra_deg"] / 15.0,
                dec_degrees=inline["dec_deg"],
                ra_mas_per_year=inline.get("pm_ra_masyr", 0.0),
                dec_mas_per_year=inline.get("pm_dec_masyr", 0.0),
                parallax_mas=inline.get("parallax_mas", 0.0),
                epoch=J2000_JD,
            )
        else:
            # Authoritative astrometry from Hipparcos by HIP number.
            df = self._hipparcos()
            if entry.hip not in df.index:
                raise KeyError(f"HIP {entry.hip} ({entry.common_name}) not in Hipparcos df")
            star = self._Star.from_dataframe(df.loc[entry.hip])

        self._star_cache[entry.hip] = star
        return star

    # -- computations --------------------------------------------------------

    def _time(self, jd_ut: float):
        return self._ts.ut1(jd=jd_ut)

    def ecliptic_longitude(self, jd_ut: float, entry: FixedStar) -> float:
        """Geocentric apparent ecliptic longitude, degrees, in the equinox OF
        THE DATE (tropical) — the number astrologers use for a fixed star."""
        star = self._star_object(entry)
        t = self._time(jd_ut)
        astrometric = self._earth.at(t).observe(star).apparent()
        _lat, lon, _dist = astrometric.ecliptic_latlon(epoch=t)
        return lon.degrees % 360.0

    def ecliptic_latlon(self, jd_ut: float, entry: FixedStar) -> tuple[float, float]:
        star = self._star_object(entry)
        t = self._time(jd_ut)
        lat, lon, _ = self._earth.at(t).observe(star).apparent().ecliptic_latlon(epoch=t)
        return lat.degrees, lon.degrees % 360.0

    def altaz(self, jd_ut: float, entry: FixedStar, lat_deg: float, lon_deg: float):
        """Topocentric altitude/azimuth — the basis for paran (rising/culminating/
        setting) relationships used in Brady-style fixed-star astrology."""
        from skyfield.api import wgs84
        star = self._star_object(entry)
        t = self._time(jd_ut)
        observer = self._earth + wgs84.latlon(lat_deg, lon_deg)
        alt, az, _ = observer.at(t).observe(star).apparent().altaz()
        return alt.degrees, az.degrees


# --------------------------------------------------------------------------- #
# Small helpers (self-contained so this file has no cross-imports)
# --------------------------------------------------------------------------- #

_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def sign_and_degree(lon: float) -> str:
    lon %= 360.0
    return f"{_SIGNS[int(lon // 30)]} {lon % 30.0:05.2f}"


def by_tradition(tag: str) -> list[FixedStar]:
    return [s for s in NAMED_STARS if tag in s.traditions]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #

def _demo() -> None:
    try:
        engine = SkyfieldFixedStarEngine()
    except ImportError:
        print("Install skyfield to run the demo:  pip install skyfield")
        print(f"\nTable holds {len(NAMED_STARS)} stars; Behenian: "
              f"{[s.common_name for s in by_tradition('behenian')]}")
        return

    # J2000 and 2026 for a few stars — note Regulus crossing Leo -> Virgo (~2012).
    import bisect  # noqa: F401 (kept minimal; not strictly needed)
    picks = [s for s in NAMED_STARS if s.common_name in ("Regulus", "Sirius", "Algol")]
    jd_2026 = 2461041.5  # 2026-01-01 00:00 UT (approx)
    print(f"{'star':10} {'@J2000':>16} {'@2026':>16}")
    for star in picks:
        lon0 = engine.ecliptic_longitude(J2000_JD, star)
        lon1 = engine.ecliptic_longitude(jd_2026, star)
        print(f"{star.common_name:10} {sign_and_degree(lon0):>16} {sign_and_degree(lon1):>16}")
    print("\n(Regulus should sit at ~29 Leo in 2000 and just into 0 Virgo by 2026 — "
          "precession at ~50\"/yr. That drift is exactly why epoch-of-date matters.)")


if __name__ == "__main__":
    _demo()
