# tzatlas bundled rules

Sourced, region- and date-bounded historical civil-time overrides for the `tzatlas` layer
(`openephem.tzatlas`). Each JSON file here holds rules that correct cases where IANA tzdata's
pre-1970 **principal-city** history is wrong for part of a zone (see `tzatlas.py` for the why).

These rules are **opt-in**. openephem never applies them on its own; a caller must ask for them:

```python
from openephem import resolve, tzatlas
r = resolve(date=(1955, 7, 15), time=(12, 0), lat=..., lon=..., atlas=tzatlas.bundled_rules())
```

## Sourcing bar (strict)

Every rule **must** cite a **primary source** — a state statute (with section), a city ordinance,
or a Federal Register / ICC / DOT boundary order (with volume & page). Commercial atlases
(Shanks/ACS *The American Atlas*) are copyrighted and may not be transcribed here, and the tz
maintainers consider them unreliable in places. Secondary sources (Wikipedia, timeanddate.com)
may guide research but are **not** acceptable as the `source`.

A rule is only worth bundling if it is **additive** — i.e. it changes the offset that default
tzdata returns for some point/date in its window. Cases that tzdata already handles (Arizona's
permanent MST, Indiana's 1972–2006 no-DST era, Michigan's exemption, the post-1980 western-Kansas
county moves) do **not** belong here.

## JSON format

A file is either a list of rule objects or `{"rules": [ ... ]}`. One rule:

```json
{
  "name": "Short unique label",
  "start": "1946-01-01",              // local civil date, inclusive
  "end":   "1967-04-30",              // local civil date, exclusive
  "action": "standard",              // "standard" | "offset" | "zone"
  "offset_hours": -6.0,              // required iff action == "offset"
  "zone": "America/Denver",          // required iff action == "zone"
  "bbox": [min_lat, min_lon, max_lat, max_lon],   // OR "polygon"
  "polygon": [[lat, lon], [lat, lon], [lat, lon]],
  "source": "Primary citation text",
  "source_url": "https://...",       // optional; appended to source
  "note": "Context / scope caveats",
  "tags": ["us-dst-1946-1966"]
}
```

`action`:
- `standard` — clocks ran on the zone's **standard** offset (strip any DST tzdata applies).
- `offset` — clocks ran at a fixed `offset_hours` (local − UTC), no DST.
- `zone` — clocks followed a different IANA `zone` (e.g. a county that was on Mountain time).

## Validating and cross-checking

- `tests/test_tzatlas_data.py` loads every bundled rule, checks it is a valid `AtlasRule` with a
  real source, and (where tzdata is present) that it is additive.
- `tools/tzatlas_backzone_check.py` compares each rule against default tzdata (and, if available, a
  `backzone`-built tzdata) and reports agreements/conflicts.
