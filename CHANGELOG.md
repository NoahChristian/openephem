# Changelog

All notable changes to **openephem** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Zodiacal Releasing** (`zodiacal_releasing.py`): Vettius Valens' releasing as pure
  computation — periods released in zodiacal order from a Hermetic Lot, each sign's
  length its ruler's Lesser Years, cascading through levels L1–L4 (years → months → …).
  The **Loosing of the Bond** (the leap to the sign opposite the level's origin after a
  full circuit) and **peak** periods (signs angular — 1st/4th/7th/10th — from the Lot of
  Fortune) are emitted as data flags, uninterpreted. All seven Hermetic Lots are
  available via `hermetic_lots()` (Fortune, Spirit, Eros, Necessity, Courage, Victory,
  Nemesis), sect-aware. `assemble()` gains `releasing_as_of=` and `releasing_lot=`
  (default `"fortune"`) → a `zodiacal_releasing` block (schema `ZR`/`ZRPeriod`/`ZRLevel`);
  peaks are reckoned from Fortune regardless of which Lot is released. Period lengths use
  the tropical year (consistent with profections and firdaria). No interpretation.
- **Firdaria** (`firdaria.py`): Persian firdaria (alfridaria) time-lords as pure
  computation — the sect-based 75-year sequence of planetary periods, each split into
  seven sub-periods (node periods subdivided too by default), with a dated timeline and
  the active major/sub lord for a date. `assemble()` gains `firdaria_as_of=` (sect is
  derived from the chart — Sun above/below the horizon) → a `firdaria` block (schema
  `Firdaria`/`FirdariaPeriod`). No interpretation.
- **Profections** (`profections.py`): annual, monthly, and daily profections as pure
  computation — the activated whole-sign house, its sign, and the sign's domicile
  ruler (Lord of the Year / Month / Day). `assemble()` gains `profection_age=` (annual
  only) and `profection_as_of=` (a date → the full annual+monthly+daily set), returning
  a `profections` block on the chart dict (schema `Profection`/`PeriodBlock`); each
  lord is enriched with its natal placement. No interpretation (dignity/condition/
  meaning) — that stays out of scope per the README and belongs to the consuming app.

### Validation
- **Extended the swisseph parity range to 1500 BC – 2500 AD** (was 0–2500):
  12169 instants over ~4000 years against the full JPL DE441 kernel. Median error
  ~0.15″, p95 ~2″; worst-case tails (Moon < 80″, Mercury < 14″, Castor < 52″) are
  documented DE431-vs-DE441 vintage drift and fixed-star proper-motion accumulation
  that grow with the baseline — astrologically negligible, not code errors.
- `run_parity.py` gains `--profile {modern,ancient}`: the tight default still gates
  the modern 0–2500 run; `ancient` applies widened, documented tolerances for the
  extended range. The production era 1900–2100 remains sub-milliarcsecond.

### Fixed
- `houses.py`: the long-term sidereal-time correction (`_ST_CORR`) was a degree-5
  polynomial fit only over years 0–2600 and diverged catastrophically when
  extrapolated before year 0 (~−1.4° by 1500 BC, flipping whole-sign cusps by a
  full sign). Added a dedicated **ancient branch** (degree-6, fit over 1550 BC–300
  AD, max fit error < 5″), applied piecewise for dates before year 0. **Modern-era
  house accuracy is unchanged.**

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
