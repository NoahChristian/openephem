# Changelog

All notable changes to **openephem** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-24

Initial public release.

### Ephemerides & bodies
- Skyfield + DE440/DE441 planetary engine — geocentric apparent, ecliptic of date;
  validated to arcseconds against Swiss Ephemeris across the years 0–2500.
- Asteroids / TNOs via JPL Horizons SPK kernels: Chiron, Ceres, Pallas, Juno,
  Vesta, Astraea, Hygeia, Eros, Eris, Sedna, asteroid Lilith.
- Mean & true lunar node; mean & osculating Black Moon Lilith.
- Fixed stars (Hipparcos, precessed to date) + a tight-orb star-conjunction pass.
- Hypothetical bodies: the eight Uranians + Trans-Pluto, Vulcan, and White Moon /
  Selena — osculating-element engine, < 0.1″ vs Swiss Ephemeris.
- Master body registry (`available_bodies()`); bodies are selectable per chart.

### Charts
- Tropical & sidereal zodiacs (Lahiri / Fagan-Bradley / KP / Raman ayanamsas,
  nakshatras / padas / rashis).
- House systems: Placidus, Koch, Regiomontanus, Campanus, Whole Sign, Equal,
  Porphyry (quadrant systems validated < 1e-6° vs `swe_houses`).
- Angles & points: Ascendant, MC, Vertex, East Point, Descendant, Imum Coeli,
  Aries/Libra Point, South Node, Co-Ascendant (Koch); Part of Fortune (sect-aware).
- Aspects, synastry (`aspects.between`), and solar / lunar / planetary returns.
- `ChartResult` is a stable, documented dict contract (`openephem.schema`).

### Packaging & quality
- Pure-Python, MIT-licensed, **no AGPL dependencies**.
- Optional extras: `[asteroids]`, `[geo]`, `[full]`, `[test]`.
- CI gates: ruff (lint) + mypy (types) + pytest with an 85% coverage gate on the
  pure-computation core, on Python 3.10–3.13 (Linux) and 3.12 (Windows).

[0.1.0]: https://github.com/NoahChristian/openephem/releases/tag/v0.1.0
