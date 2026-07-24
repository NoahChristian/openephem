# openephem

[![CI](https://github.com/NoahChristian/ElpisWeb/actions/workflows/ci.yml/badge.svg)](https://github.com/NoahChristian/ElpisWeb/actions/workflows/ci.yml)

**A permissive, Swiss-Ephemeris-validated ephemeris & chart engine.**
MIT-licensed, no AGPL — validated to arcseconds against Swiss Ephemeris across
**year 0–2500**.

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
| **Zodiacs** | tropical **and** Vedic sidereal (Lahiri, Fagan-Bradley, Krishnamurti, Raman) + nakshatras/padas/rashis |
| **Time & place** | timezone/DST/historical/LMT (IANA tzdata), Julian↔Gregorian calendar, offline coord→timezone, place geocoding |
| **Output** | serializable chart dict, self-contained **SVG chart wheel**, zero-dep **HTTP API** |

## Validation — parity vs swisseph: **PASS (year 0–2500)**

**3044 instants over 2500 years**, Skyfield candidate vs swisseph authority with
ΔT aligned so the test isolates the ephemeris. Candidate ephemeris in two
segments: DE441 part-1 (0–1550, since DE440 starts at 1550) and DE440 (1550–2500).
Max ecliptic-longitude error per group (worst case over the full 2500 years):

| Group | max err | Group | max err |
|-------|---------|-------|---------|
| Sun + Jupiter–Pluto | **< 0.4"** | Mean / True Node | 2.6" / 2.6" |
| Mercury / Venus / Mars | < 3.6" | Mean / Oscu Lilith | 18.4" / 1.7" |
| Moon | < 27" *(note)* | 32 fixed stars | < 29" *(Castor)* |
| Chiron + Ceres/Pallas/Juno/Vesta | < 11" *(note)* | Houses (all 7) | **< 20"** |

Zero real sign-flips. **Within 1900–2100 the whole set agrees to milliarcsec–
tenths**; the table is the *worst case over 2500 years*, dominated by physical /
documented antiquity effects (all astrologically negligible, none a code error):

* **ΔT** diverges past ~2100 (extrapolation) and is ~3 h by year 0 — a real
  timekeeping uncertainty, aligned out in the parity test; production uses
  Skyfield's ΔT (agrees with swisseph 1900–2100).
* **Moon / inner planets** in deep antiquity — DE431 (swisseph) vs DE441
  (candidate) ephemeris-vintage divergence.
* **Asteroids** — JPL vs swisseph use *different orbit solutions* that drift over
  centuries (≤ 11" = 0.003°).
* **Fixed stars** — high-proper-motion multiples (Castor, Altair) as swisseph's
  vs Hipparcos's proper motions accumulate over 2500 years.

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
# generate the swisseph oracle, then check the permissive engines against it:
python validation/generate_oracle.py --ephe-path ./ephe --fixed-stars \
    --start 0 --end 2500 --step-days 120 --out ./fixtures
python validation/run_parity.py --fixtures ./fixtures --de440 de440.bsp --kernel-dir ./kernels
```
Swiss Ephemeris `.se1` data and `sefstars.txt` (for the oracle authority) are
**not** included — download them from the swisseph distribution. No AGPL code or
data is redistributed in this repo.

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
