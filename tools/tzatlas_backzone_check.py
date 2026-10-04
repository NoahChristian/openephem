#!/usr/bin/env python3
"""Cross-check bundled tzatlas rules against tzdata (and, if available, a backzone build).

For every rule it samples the region centroid on the rule's start date and compares the offset
the rule yields against what *default* tzdata returns there:

  * ADDITIVE  - the rule changes the offset (this is the point of a rule);
  * REDUNDANT - the rule echoes default tzdata (it probably belongs in tzdata, not here).

If a backzone-built tzdata is available (set TZDIR to a zoneinfo tree compiled with the tz
`backzone` file, or `pip install tzdata-legacy` and point TZDIR at it), the tz maintainers'
own pre-1970 history for the rule's zone is printed alongside for comparison.

    python tools/tzatlas_backzone_check.py            # bundled rules
    python tools/tzatlas_backzone_check.py rules.json # a specific file
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from openephem import tzatlas  # noqa: E402
from openephem.timeplace import resolve  # noqa: E402


def _centroid(rule):
    if rule.bbox is not None:
        return (rule.bbox[0] + rule.bbox[2]) / 2, (rule.bbox[1] + rule.bbox[3]) / 2
    poly = rule.polygon
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def _backzone_note(zone, when):
    """tz maintainers' pre-1970 offset for `zone`, if a backzone tzdata build is on TZDIR."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        dt = datetime(when.year, when.month, when.day, 12, tzinfo=ZoneInfo(zone))
        off = dt.utcoffset()
        return f"{off.total_seconds() / 3600:+g}" if off is not None else "?"
    except Exception as e:  # noqa: BLE001
        return f"(unavailable: {e})"


def main(argv):
    rules = (tzatlas.load_rules(open(argv[1], encoding="utf-8").read())
             if len(argv) > 1 else tzatlas.bundled_rules())
    if not rules:
        print("no rules to check (bundled ruleset is empty).")
        return 0
    backzone_on = "TZDIR" in os.environ
    print(f"checking {len(rules)} rule(s)  "
          f"(backzone build: {'TZDIR=' + os.environ['TZDIR'] if backzone_on else 'not set'})\n")
    redundant = 0
    for r in rules:
        lat, lon = _centroid(r)
        y, m, d = r.start.year, r.start.month, r.start.day
        base = resolve(date=(y, m, d), time=(12, 0), lat=lat, lon=lon)
        over = resolve(date=(y, m, d), time=(12, 0), lat=lat, lon=lon, atlas=[r])
        additive = over.offset_hours != base.offset_hours
        if not additive:
            redundant += 1
        flag = "ADDITIVE " if additive else "REDUNDANT"
        zone = r.zone or base.tz
        bz = _backzone_note(zone, r.start) if backzone_on else "-"
        print(f"[{flag}] {r.name}")
        print(f"    @({lat:.3f},{lon:.3f}) {r.start}: default UTC{base.offset_hours:+g} "
              f"-> rule UTC{over.offset_hours:+g}   zone={zone} backzone={bz}")
        print(f"    source: {r.source}")
    print(f"\n{len(rules) - redundant} additive, {redundant} redundant.")
    return 1 if redundant else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
