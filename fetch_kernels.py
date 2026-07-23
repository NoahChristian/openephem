#!/usr/bin/env python3
"""
fetch_kernels.py — generate asteroid SPK (.bsp) kernels from JPL Horizons.

Turns the manual "Horizons browser -> SPK File -> download" chore into one
reproducible command. Uses ONLY the Python standard library (urllib/json/base64),
so it runs anywhere without installing anything.

The Horizons API (public, no auth) integrates each small body's orbit over the
requested span and returns the SPK file base64-encoded. Output is JPL/NASA public
domain (17 U.S.C. sec.105) — safe to ship with attribution.

    python fetch_kernels.py --out ./kernels --start 1550-01-01 --stop 2650-01-01

By default it generates the five bodies in asteroids_skyfield.ASTEROID_TABLE
(Chiron, Ceres, Pallas, Juno, Vesta). The span defaults to DE440's coverage.

Notes / caveats
---------------
* Span vs Chiron validity: Chiron's orbit is only reliable from ~700 AD onward
  (chaotic before); a very early START may be refused or unreliable.
* Horizons may cap SPK duration; if a request errors, shorten the span.
* The API response shape can evolve — this looks for a base64 'spk' field and
  falls back to printing the raw error so failures are visible, not silent.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def _import_table():
    """Pull the body list from asteroids_skyfield so the two stay in sync."""
    try:
        import asteroids_skyfield as a
        return [(x.name, x.number, x.kernel) for x in a.ASTEROID_TABLE]
    except Exception:  # noqa: BLE001 — fall back to a static copy
        return [("Chiron", 2060, "chiron.bsp"), ("Ceres", 1, "ceres.bsp"),
                ("Pallas", 2, "pallas.bsp"), ("Juno", 3, "juno.bsp"),
                ("Vesta", 4, "vesta.bsp")]


def fetch_one(number: int, start: str, stop: str, timeout: float = 120.0) -> bytes:
    """Return the raw .bsp bytes for one numbered small body, or raise."""
    params = {
        "format": "json",
        "EPHEM_TYPE": "SPK",
        "OBJ_DATA": "NO",
        "COMMAND": f"'{number};'",     # trailing ';' => small-body designation
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
    }
    url = HORIZONS_API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", "replace")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError(f"non-JSON response: {payload[:300]}")

    if "spk" in data and data["spk"]:
        return base64.b64decode(data["spk"])
    # Surface whatever Horizons said instead of failing silently.
    msg = data.get("error") or data.get("result") or json.dumps(data)[:400]
    raise RuntimeError(f"no SPK returned: {msg}")


def run(args) -> int:
    os.makedirs(args.out, exist_ok=True)
    bodies = _import_table()
    if args.only:
        wanted = {n.lower() for n in args.only}
        bodies = [b for b in bodies if b[0].lower() in wanted]

    failures = 0
    for name, number, kernel in bodies:
        dest = os.path.join(args.out, kernel)
        if os.path.exists(dest) and not args.force:
            print(f"  [skip] {name}: {dest} exists (use --force to regenerate)")
            continue
        try:
            print(f"  [get ] {name} ({number}) {args.start}..{args.stop} ...", flush=True)
            blob = fetch_one(number, args.start, args.stop, args.timeout)
            with open(dest, "wb") as fh:
                fh.write(blob)
            print(f"  [ok  ] {name}: wrote {dest} ({len(blob):,} bytes)")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [FAIL] {name}: {exc}", file=sys.stderr)

    print(f"\n{'done' if failures == 0 else f'{failures} failed'}; kernels in {args.out}")
    return 0 if failures == 0 else 1


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate asteroid SPK kernels from JPL Horizons.")
    p.add_argument("--out", default="./kernels", help="output directory for .bsp files")
    p.add_argument("--start", default="1550-01-01", help="SPK start date (matches DE440)")
    p.add_argument("--stop", default="2650-01-01", help="SPK stop date (matches DE440)")
    p.add_argument("--only", nargs="*", help="subset of body names (default: all)")
    p.add_argument("--force", action="store_true", help="regenerate even if file exists")
    p.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout seconds")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args()))
