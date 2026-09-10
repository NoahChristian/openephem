# openephem

[![CI](https://github.com/NoahChristian/openephem/actions/workflows/ci.yml/badge.svg)](https://github.com/NoahChristian/openephem/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/openephem.svg)](https://pypi.org/project/openephem/)
[![Python](https://img.shields.io/pypi/pyversions/openephem.svg)](https://pypi.org/project/openephem/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A permissive, Swiss-Ephemeris-validated ephemeris & chart engine.**
MIT-licensed, no AGPL — validated to arcseconds against Swiss Ephemeris across
**1500 BC – 2500 AD**.

Most "open" astrology libraries wrap `pyswisseph`, which is **AGPL**: use it in a
network service and you must publish your whole app's source (or buy a commercial
license). `openephem` is built entirely on **permissive / public-domain** sources
(Skyfield MIT, JPL/NASA public domain, ESA Hipparcos, IANA tzdata, OSM), so you
can ship it in a closed-source product with no copyleft obligation — and it's
checked against swisseph so you don't sacrifice accuracy for freedom.

## Install

```bash
pip install openephem            # core: planets + fixed stars + chart math
pip install "openephem[full]"    # + asteroids (spiceypy) + geocoding (geopy/tz)
```
Extras: `openephem[asteroids]` (Chiron/Ceres/Pallas/Juno/Vesta),
`openephem[geo]` (place-name → lat/lon → timezone). Pure Python — no compiler.

Ephemeris **data** (JPL DE440 ~114 MB, Hipparcos, asteroid SPK kernels) is
**fetched at runtime**, not shipped: Skyfield auto-downloads DE440/Hipparcos on
first use; asteroid kernels are generated with `openephem-fetch-kernels`.

## Quick start

```python
from openephem import resolve, assemble, render_svg

moment = resolve(date=(1990, 5, 15), time=(14, 30), place="New York, NY")
chart  = assemble(moment, house_system="Placidus")     # tropical
svg    = render_svg(chart, title="Natal chart")

vedic  = assemble(moment, zodiac="sidereal", ayanamsa="lahiri")  # nakshatras + rashis
```
Everything degrades gracefully: without the ephemeris data (or the optional
deps) you still get houses, angles, and aspects, plus warnings for what's missing.

## What it computes

| | |
|---|---|
| **Bodies** | Sun–Pluto, Moon, mean/true Node, mean/osculating Lilith, **Chiron + Ceres/Pallas/Juno/Vesta**, 32 named fixed stars |
| **Houses** | Placidus, Koch, Regiomontanus, Campanus, Whole Sign, Equal, Porphyry, + Asc/MC/Vertex/East Point |
| **Aspects** | majors + optional minors, configurable orbs, applying/separating |
| **Profections** | annual/monthly/daily profected place + sign + domicile ruler (Lord of the Year/Month/Day) — pure data, no interpretation |
| **Firdaria** | Persian firdaria time-lords (sect-based order), major + sub periods with a dated timeline and the active lord(s) — pure data |
| **Zodiacs** | tropical **and** Vedic sidereal (Lahiri, Fagan-Bradley, Krishnamurti, Raman) + nakshatras/padas/rashis |
| **Time & place** | timezone/DST/historical/LMT (IANA tzdata), Julian↔Gregorian calendar, offline coord→timezone, place geocoding |
| **Output** | serializable chart dict, self-contained **SVG chart wheel**, zero-dep **HTTP API** |

## Validation — parity vs swisseph: **PASS (1500 BC – 2500 AD)**

**12169 instants over ~4000 years**, Skyfield candidate vs swisseph authority with
ΔT aligned so the test isolates the ephemeris. Candidate ephemeris: JPL **DE441**
(covers −13200…+17191), so a single kernel spans the whole range. Across the full
span the median error is **~0.15"** and the 95th percentile **~2"**; the table
below is the *worst case* per group over the full 4000 years:

| Group | max err | Group | max err |
|-------|---------|-------|---------|
| Sun + Jupiter–Pluto | **< 3.5"** | Mean / True Node | 8.5" / 38.6" |
| Mercury / Venus / Mars | < 14" | Mean / Oscu Lilith | 51" / 4" |
| Moon | < 80" *(note)* | 32 fixed stars | < 52" *(Castor)* |
| Chiron + Ceres/Pallas/Juno/Vesta | < 11" *(AD only, note)* | Houses (all 7) | **< 21"** |

Zero real sign-flips. **Within 1900–2100 the whole set agrees to milliarcsec–
tenths** (Sun max 0.002", Moon 0.003", houses < 3.5", Castor 1.5" — the tight
`--profile modern` gate); the table is the *worst case over 4000 years*, dominated
by physical / documented antiquity effects (all astrologically negligible — 80" is
0.022° — none a code error), which grow with the baseline and so are larger than
the year-0 figures:

* **ΔT** diverges past ~2100 (extrapolation) and is ~3 h by year 0 (larger before)
  — a real timekeeping uncertainty, aligned out in the parity test; production uses
  Skyfield's ΔT (agrees with swisseph 1900–2100).
* **Moon / inner planets** in deep antiquity — DE431 (swisseph) vs DE441
  (candidate) ephemeris-vintage divergence, ~2–3× the year-0 size over a 3500-yr
  baseline.
* **Asteroids** — validated over their JPL-Horizons kernel range (**AD only**; the
  kernels don't reach BC), JPL vs swisseph *different orbit solutions* drifting
  ≤ 11" (0.003°) over centuries.
* **Fixed stars** — high-proper-motion multiples (Castor, Altair) as swisseph's
  vs Hipparcos's proper motions accumulate ~linearly over the 3500-yr baseline
  (Castor 29"→52", Altair 16"→46").

The extended range uses the widened-but-documented `--profile ancient` tolerances
(the tight defaults still gate the modern 0–2500 run). Pre-1 AD sidereal time uses
a dedicated long-term correction branch in `houses.py` — the modern polynomial
diverges if extrapolated past year 0.

How the tricky quantities match swisseph (all coefficients fit **offline** vs
swisseph — the numbers are astronomical facts, not copyrightable):
osculating Node/Lilith from Skyfield's of-date ecliptic; mean Node/Lilith =
Meeus mean elements + nutation-in-longitude (+ the `2·(perigee−node)` term for
Lilith); houses use apparent sidereal time (with a long-term precession
correction) + true obliquity; asteroids read Horizons SPK **type 21** (which
jplephem can't) via `spiceypy`, then Skyfield does the of-date conversion.

Reproduce it yourself — see **Development & validation** below.

## Chart API + SVG

```bash
openephem-serve --port 8080          # zero-dependency stdlib HTTP service
```
`POST /chart` → chart JSON + embedded SVG; `POST /chart.svg` → image;
`GET /health`. Body:
```json
{"date":[1990,5,15],"time":[14,30],"place":"New York, NY","house_system":"Placidus",
 "zodiac":"tropical"}
```
Run it behind your web server and add auth there — the service does none itself.

## Layout

```
src/openephem/        # the installable, MIT, swisseph-free package
  planets_skyfield  asteroids_skyfield  fixed_stars   # position engines
  houses  aspects  vedic                              # chart math (pure stdlib)
  timeplace  chart  wheel  service  fetch_kernels     # pipeline + output
validation/           # dev tools — NOT installed; import pyswisseph (AGPL)
  generate_oracle.py  run_parity.py
```

## Development & validation

The validation harness compares the permissive engines against swisseph. It is
**not** part of the shipped package; running it is your own choice and needs
`pyswisseph` (AGPL) installed separately:

```bash
pip install -e ".[full]" pyswisseph        # editable install + swisseph, locally
openephem-fetch-kernels --out ./kernels    # asteroid SPK kernels (Horizons)

# Modern range (0–2500), tight default tolerances — the CI gate:
python validation/generate_oracle.py --ephe-path ./ephe --fixed-stars \
    --start 0 --end 2500 --step-days 120 --out ./fixtures
python validation/run_parity.py --fixtures ./fixtures --de440 de440.bsp --kernel-dir ./kernels

# Extended range (1500 BC – 2500 AD): needs the full JPL DE441 kernel and the
# swisseph BC ".se1" files (…m06/m12/m18); use the widened, documented tolerances:
#   curl -O https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de441.bsp   # 3.3 GB, covers −13200…+17191
python validation/generate_oracle.py --ephe-path ./ephe --fixed-stars \
    --start -1499 --end 2499 --step-days 120 --out ./fixtures_1500bc
python validation/run_parity.py --fixtures ./fixtures_1500bc --de440 de441.bsp \
    --kernel-dir ./kernels --profile ancient
```
Swiss Ephemeris `.se1` data (AD blocks `_00…_24` **and** the BC "minus" blocks
`…m06/m12/m18` for the ancient range) and `sefstars.txt` are **not** included —
download them from the swisseph distribution. Asteroids are validated over their
Horizons-kernel range only (AD; they don't reach BC, and the 3.3 GB DE441 exceeds
CSPICE's 2 GB DAF limit — use the smaller `de440s.bsp` for the asteroid pass). No
AGPL code or data is redistributed in this repo.

## Tests

```bash
pip install -e ".[test]" && pytest
```
A fast, **offline, data-free** suite (houses, aspects, vedic, timeplace, wheel,
chart — no network, no ephemeris files). Exactness tests that compare the house
systems against `swe_houses` run automatically **when `pyswisseph` is installed**
and skip otherwise, so the MIT test run needs no AGPL dependency. CI (GitHub
Actions) runs it on Python 3.10–3.13 (Linux + Windows) and proves the wheel
builds and installs.

## Licensing

MIT (see [`LICENSE`](../../LICENSE)). Third-party libraries/data keep their own
licenses (Skyfield MIT, spiceypy/CSPICE, Moshier PD, JPL/NASA PD, ESA Hipparcos,
OpenStreetMap ODbL, IANA tzdata PD) — full notices in `references.txt`.
**Swiss Ephemeris (AGPL) is not distributed here**; it is used only by the
optional offline validation tools.

## Out of scope (by design)

* **Interpretation / "reading" layer** — turning a computed chart into meaning is
  editorial content, not computation; it belongs to the consuming application.
* **Site integration** (WordPress, auth, hosting) — this is a self-contained
  engine + service; wiring it into a website is the consumer's job.

## Authors

© 2026 **Elizabeth Huston, Ph.D.** and **Noah Christian, Ph.D.**  
Contact: elpisastrology@gmail.com · elpisastrology.com and noahchristian@gmail.com
