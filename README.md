# Ephemeris migration — oracle generator

Reference-data harness for replacing Swiss Ephemeris with a permissively-licensed
engine (Moshier is the first candidate) **without** taking on AGPL obligations.

> **Status for this project:** as of the last audit, the live WordPress site does
> **not** use Swiss Ephemeris anywhere (no `.se1` files, no `swe_*` code, no
> astrology engine). Readings are human-delivered via WooCommerce + Contact Form 7
> intake forms. This harness is **forward-looking** — only needed if/when an
> automated chart/transit calculator is built into the site.

## Why this exists

If you ever compute charts server-side, Swiss Ephemeris under **AGPL** forces you
to publish your app's source to every network user (AGPL §13), unless you buy the
Astrodienst **Professional License**. The alternative is a permissive engine —
but you must prove it's accurate enough. This harness generates a "golden"
dataset from swisseph so a replacement can be validated against it.

## Licensing hygiene (non-negotiable)

- Run the generator **offline**, as a build/test step.
- Computed positions are **facts** (not copyrightable) → committing the emitted
  JSON/CSV fixtures is clean.
- **Never** commit `.se1` data files or swisseph source into the product repo.
- The engine that ships in production must be the **permissive** one, never
  swisseph — unless you hold the Professional License.

## Usage

```bash
pip install -r requirements.txt

# quick smoke run (weekly grid, 1950–2100)
python generate_oracle.py --out ./fixtures

# with Chiron + best precision (point at your .se1 files)
python generate_oracle.py --ephe-path /path/to/ephe --out ./fixtures

# add interpretation-critical sign-ingress boundary cases
python generate_oracle.py --boundaries --out ./fixtures

# fixed stars: swisseph authority + Skyfield (MIT) parity column
python generate_oracle.py --fixed-stars --fixstar-candidate --out ./fixtures

# fixed-star module standalone demo (shows Regulus precessing Leo -> Virgo)
python fixed_stars.py
```

## Outputs

| File | Contents |
|------|----------|
| `fixtures/oracle.json` | Full records: Swiss (authority) + Moshier + houses + Δt + meta |
| `fixtures/deltas.csv`  | Per-(instant, body) Swiss-vs-Moshier delta + `sign_flip` flag |
| `fixtures/fixstars.json` | Fixed-star longitudes: swisseph authority (+ Skyfield candidate) |
| `fixtures/fixstar_deltas.csv` | Per-(year, star) Swiss-vs-Skyfield delta + `sign_flip` flag |
| stdout summary | max/mean arcsec error, **sign-flip count**, **Chiron/Moshier gaps** |

## Reading the verdict

- **`SIGN FLIPS > 0`** → Moshier moved a body across a sign cusp relative to
  Swiss. Interpretation-breaking; investigate before trusting Moshier there.
- **`Moshier gaps > 0`** → bodies Moshier can't do at all (Chiron/asteroids).
  If your readings use them, Moshier alone is insufficient — you need a Swiss/
  asteroid source or a licensed swisseph for those bodies.

## Resolved asteroid / Chiron strategy (permissive, no AGPL)

The Moshier gap the harness flags is real but bounded — it's basically just Chiron.

- **Black Moon Lilith is NOT an asteroid.** It's the lunar apogee (a computed
  point), so Moshier/astronomy-engine handle it natively — no asteroid data.
  (`MeanLilith` is correctly `moshier=True` in the body table.)
- **Chiron** (and the separate, rarely-used **asteroid 1181 Lilith**) DO need an
  asteroid ephemeris. Permissive, commercial-safe source:
  - **Data:** JPL Horizons small-body **SPK (`.bsp`) kernel** for 2060 Chiron
    (SPK-ID `20002060`). JPL/NASA data is a US-government work → not copyrightable
    (17 U.S.C. §105), effectively public domain.
  - **Engine:** **Skyfield (MIT)** loads the `.bsp` and returns geocentric
    ecliptic lon/lat via `frame_latlon(ecliptic_frame)`.
  - Prefer this over MPC `MPCORB.DAT` elements (MPC licensing is murkier).
- **Caveats:** Chiron's orbit is only reliable from ~700 AD onward (chaotic before;
  swisseph has the same limit). NASA's "commercial" brand caveats concern imagery/
  logos/endorsement, not ephemeris numbers.
- **Do NOT** use Kerykeion/flatlib as "permissive" — they wrap pyswisseph (AGPL).
- **Fixed stars** (Regulus, Sirius, Algol, ...) are NOT solar-system bodies and
  need NO asteroid/SPK data — just catalog astrometry + precession. Implemented
  in `fixed_stars.py` with **Skyfield (MIT)**; star coordinates are facts (pulled
  from Hipparcos by HIP, or frozen inline for a zero-external-data build).
  Validate via the `--fixed-stars --fixstar-candidate` oracle columns.

Resulting stack: Moshier/astronomy-engine for Sun-Pluto + nodes + Black Moon
Lilith; JPL-SPK + Skyfield for Chiron (and asteroid 1181 if ever offered);
Skyfield for fixed stars; in-repo formulas for houses + ayanamsa.

## Build status & validation workflow

Engine decision: **Skyfield + DE440** for planets (unifies with Chiron/asteroids/
stars on one MIT engine). Swiss Ephemeris stays the **authority** in the oracle.
Vedic/sidereal is **out of scope**. Asteroids: **Chiron + Ceres, Pallas, Juno, Vesta**.

Files:

| File | Role | Status |
|------|------|--------|
| `generate_oracle.py` | swisseph authority fixtures (+ RA/Dec, Δt, houses, ingresses, stars) | built, syntax-checked |
| `planets_skyfield.py` | Skyfield+DE440 planets + Moon + mean node/Lilith | built, syntax-checked |
| `asteroids_skyfield.py` | Chiron/Ceres/Pallas/Juno/Vesta via JPL SPK (spiceypy type-21 read) | **parity-validated** (< 1.9") |
| `fixed_stars.py` | fixed stars (Hipparcos + Skyfield) | built, syntax-checked |
| `fetch_kernels.py` | generate asteroid SPK kernels from Horizons API | **built + live-tested** (real chiron.bsp fetched) |
| `run_parity.py` | validate all engines (planets/asteroids/stars/houses) vs oracle; CI gate | built; control-flow smoke-tested |
| `houses.py` | Asc/MC/Vertex/EP + Whole Sign/Equal/Porphyry/Placidus | built + **run-tested** (cusps monotonic, antipodal) |
| `aspects.py` | aspect detection + orbs + applying/separating | built + **run-tested** (demo correct) |
| `timeplace.py` | local date/time/place -> JD(UT): tz/DST/LMT + calendar + geocoding | built + **live-tested** (geocode->tz->JD end-to-end) |
| `chart.py` | assemble full chart (bodies + houses + aspects) from a birth moment | built + **run-tested** (graceful degrade) |
| `wheel.py` | self-contained SVG chart wheel (zero deps) | built + **run-tested** (valid SVG, no NaN) |
| `service.py` | stdlib HTTP API: `/chart`, `/chart.svg`, `/health` | built + **run-tested** (live endpoints) |

End-to-end workflow:

```bash
pip install -r requirements.txt

# 0. asteroid kernels (scripted, no manual Horizons browsing)
python fetch_kernels.py --out ./kernels          # chiron/ceres/pallas/juno/vesta .bsp

# 1. oracle — align authority onto DE440 so residuals are pure convention
python generate_oracle.py --authority jpleph --jpl-file de440.bsp \
    --ephe-path /path/to/ephe --fixed-stars --fixstar-candidate \
    --boundaries --out ./fixtures

# 2+3. validate the permissive engines against the oracle (exits nonzero on failure)
python run_parity.py --fixtures ./fixtures --de440 de440.bsp --kernel-dir ./kernels
```

## Chart API (chart.py / wheel.py / service.py)

```bash
python service.py --port 8080          # zero-dependency stdlib HTTP service
```
`POST /chart` returns chart JSON + embedded SVG; `POST /chart.svg` returns the
image; `GET /health` for liveness. Request body:
```json
{"date":[1990,5,15],"time":[14,30],"place":"New York, NY, USA","house_system":"Placidus"}
```
Bodies need skyfield + DE440 (+ kernels); without them the chart still returns
houses / angles / aspects + warnings. Run it behind the web server and add auth
there — the service does none itself.

## Validation — parity vs swisseph: **PASS**

Full run: 609 instants, 1950-2050, Skyfield+DE440s candidate vs swisseph SWIEPH
(DE431) authority. Max ecliptic-longitude error per group:

| Group | max err | Group | max err |
|-------|---------|-------|---------|
| 9 planets (Sun-Pluto) | **< 0.26"** | Mean / True Node | 18.7" / **0.04"** |
| Moon | **1.9"** | Mean / Oscu Lilith | **2.3"** / 1.4" |
| Chiron + Ceres/Pallas/Juno/Vesta | **< 1.9"** | 32 fixed stars | **< 0.85"** |
| Houses (Placidus/WholeSign/Equal): Asc/MC/Vtx/EP/cusps | **< 38"** | | |

Zero sign-flips. `RESULT: PASS`. Reproduce with the workflow above.

How the tricky ones are done:
* **TrueNode / OscuLilith** — osculating orbit expressed in Skyfield's ecliptic-
  of-date frame (no extra precession term — that was the bug the harness caught).
* **MeanLilith** — mean apogee + swisseph's periodic term `2*(perigee - node)`
  (period ~1095 d, amp ~416"); coefficients fit offline against swisseph (facts),
  residual ~1" RMS.
* **Asteroids** — Horizons SPK are data **type 21**, which jplephem can't read;
  `spiceypy` (CSPICE, MIT) reads them, Skyfield does the of-date conversion.
* **MeanNode ~18"** — Meeus-vs-swisseph mean-element difference (a *mean* point;
  well within tolerance). **Outer planets** use DE440 barycenters (still sub-arcsec).
  **Houses** use mean sidereal time + mean obliquity (nutation omitted, < ~20").

## Still deferred (low priority)

* **Koch / Regiomontanus / Campanus** house systems — raise `NotImplementedError`;
  `run_parity.py` skips them (no unvalidated trig shipped). Placidus + Whole Sign
  cover the common cases.

## Roadmap

1. ~~Osculating TrueNode / OscuLilith~~ — **done** (first pass, parity-gated).
2. ~~Houses + Asc/MC/Vertex + aspects~~ — **done** except Koch/Regiomontanus/
   Campanus (queued). Aspects engine complete.
3. ~~Time/timezone/DST/LMT + calendar (Julian pre-1582) + geocoding~~ — **done**
   (`timeplace.py`, live-tested: IANA tzdata + offline `timezonefinder` +
   `geopy`/Nominatim, Google optional). Handles unknown time + DST ambiguity/gaps.
4. ~~Chart-wheel rendering (SVG) + API service~~ — **done** (`wheel.py` zero-dep
   SVG; `service.py` stdlib HTTP API `/chart` `/chart.svg` `/health` — run-tested).
5. ~~Run the numeric parity table~~ — **done, PASS** (see Validation above); all
   bodies/houses/stars match swisseph (asteroids fixed via spiceypy, MeanLilith
   via the periodic correction).
6. **Next:** WordPress/WooCommerce integration + auth in front of the service.
7. Close the remaining quadrant house systems (Koch/Regio/Campanus).
