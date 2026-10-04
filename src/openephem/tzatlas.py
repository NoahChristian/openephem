"""
tzatlas.py - historical civil-time overrides layered on top of IANA tzdata.

Why this exists
---------------
IANA tzdata is the right default, but it is explicitly *not* an atlas of local
historical time. Its scope rule is that each zone is accurate from 1970 on; a
region whose clocks have agreed since 1970 shares one zone, and that zone's
pre-1970 history is the history of its **principal city**. So `America/Chicago`
covers all of Kansas, but its 1946-1966 rules are Chicago's - and Chicago kept
daylight saving time in years when most of Kansas (and Missouri, Iowa, ...) did
not. Before the Uniform Time Act took effect (1967-04-30), US daylight time was
a local option, and before the ICC/DOT boundary moves of the 1960s-70s some
areas sat in a different standard zone than today.

Birth charts are dominated by pre-1970 dates, so a chart engine cannot take the
principal-city history on faith. This module provides:

1. `AtlasRule` - a small, auditable record: a region (bbox or polygon), a local
   date range, and what the clocks actually did there (a fixed offset, "standard
   time of the IANA zone, no DST", or a different IANA zone), plus a citation.
2. `match()` - first-matching-rule lookup for (lat, lon, local date/time).
3. `principal_city_warnings()` - flags moments where the IANA result is known to
   be a principal-city extrapolation, so callers can verify instead of silently
   trusting it.

No rules are bundled yet: every rule must carry a primary source (statute,
ordinance, newspaper notice). Commercial atlases (e.g. Shanks/ACS) are
copyrighted and may not be transcribed into this MIT package. Callers pass their
own vetted rules via `resolve(atlas=[...])`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

Action = str  # "offset" | "standard" | "zone"

# Uniform Time Act of 1966 took effect on this date; before it, US daylight time
# was a state/local option and IANA's US zones carry principal-city history.
UNIFORM_TIME_ACT_EFFECTIVE = date(1967, 4, 30)
# tzdata's guaranteed-accuracy horizon.
TZDATA_HORIZON = date(1970, 1, 1)

# Zones whose pre-1970 history is a single principal city's while covering
# large US regions with divergent local practice.
US_ZONES = frozenset({
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "America/Phoenix", "America/Detroit",
    "America/Boise", "America/Anchorage", "America/Juneau", "America/Sitka",
    "America/Nome", "America/Yakutat", "America/Metlakatla", "America/Adak",
    "America/Menominee", "Pacific/Honolulu",
})
US_ZONE_PREFIXES = ("America/Indiana/", "America/Kentucky/", "America/North_Dakota/")


def is_us_zone(tzname: str) -> bool:
    return tzname in US_ZONES or tzname.startswith(US_ZONE_PREFIXES)


@dataclass(frozen=True)
class AtlasRule:
    """One historical civil-time fact for a region and local date range.

    region: either a bbox ``(min_lat, min_lon, max_lat, max_lon)`` or a polygon
        given as a sequence of ``(lat, lon)`` vertices (first vertex need not
        repeat). Exactly one of ``bbox`` / ``polygon`` must be set.
    start / end: local civil dates, inclusive start, exclusive end.
    action:
        "offset"   - clocks ran at ``offset_hours`` (local - UTC), no DST.
        "standard" - clocks ran on the *standard* offset of the IANA zone in
                     effect (``zone`` if given, else the resolved zone); any DST
                     tzdata applies for that date is removed.
        "zone"     - clocks followed IANA ``zone`` instead (e.g. a county that
                     was on Mountain time: ``zone="America/Denver"``).
    source: citation for the rule (required - unsourced rules are rejected).
    """
    name: str
    start: date
    end: date
    action: Action
    source: str
    bbox: tuple[float, float, float, float] | None = None
    polygon: tuple[tuple[float, float], ...] | None = None
    offset_hours: float | None = None
    zone: str | None = None
    note: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if (self.bbox is None) == (self.polygon is None):
            raise ValueError(f"{self.name}: set exactly one of bbox= or polygon=")
        if self.polygon is not None and len(self.polygon) < 3:
            raise ValueError(f"{self.name}: polygon needs at least 3 vertices")
        if not self.source.strip():
            raise ValueError(f"{self.name}: a source citation is required")
        if self.end <= self.start:
            raise ValueError(f"{self.name}: end must be after start")
        if self.action == "offset":
            if self.offset_hours is None:
                raise ValueError(f"{self.name}: action='offset' needs offset_hours")
        elif self.action == "zone":
            if not self.zone:
                raise ValueError(f"{self.name}: action='zone' needs zone=")
        elif self.action != "standard":
            raise ValueError(f"{self.name}: unknown action {self.action!r}")

    def contains(self, lat: float, lon: float) -> bool:
        if self.bbox is not None:
            a, b, c, d = self.bbox
            return a <= lat <= c and b <= lon <= d
        assert self.polygon is not None
        return _point_in_polygon(lat, lon, self.polygon)

    def applies(self, lat: float, lon: float, when: date) -> bool:
        return self.start <= when < self.end and self.contains(lat, lon)


def _point_in_polygon(lat: float, lon: float, poly) -> bool:
    """Even-odd ray cast in (lon, lat) plane. Boundary points count as inside."""
    inside = False
    n = len(poly)
    for i in range(n):
        y1, x1 = poly[i]
        y2, x2 = poly[(i + 1) % n]
        # on-segment check (collinear and within bounds)
        cross = (x2 - x1) * (lat - y1) - (y2 - y1) * (lon - x1)
        if abs(cross) < 1e-12 and min(x1, x2) <= lon <= max(x1, x2) \
                and min(y1, y2) <= lat <= max(y1, y2):
            return True
        if (y1 > lat) != (y2 > lat):
            x_at = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_at:
                inside = not inside
    return inside


def match(rules, lat: float, lon: float, when: date | datetime) -> AtlasRule | None:
    """First rule (in the given order) covering this place and local date."""
    d = when.date() if isinstance(when, datetime) else when
    for r in rules or ():
        if r.applies(lat, lon, d):
            return r
    return None


def principal_city_warnings(tzname: str, when: date | datetime, *,
                            dst_hours: float, derived: bool) -> list[str]:
    """Warnings for moments where an IANA result is a principal-city
    extrapolation. ``dst_hours`` is the DST component tzdata applied;
    ``derived`` is True when the zone came from a coordinate lookup rather
    than from the caller."""
    d = when.date() if isinstance(when, datetime) else when
    out: list[str] = []
    if d >= TZDATA_HORIZON:
        return out
    if is_us_zone(tzname) and d < UNIFORM_TIME_ACT_EFFECTIVE:
        if dst_hours:
            out.append(
                f"pre-1967 US daylight time: tzdata applied {dst_hours:+g}h DST from "
                f"{tzname}'s principal-city history, but DST was a local option "
                "before the Uniform Time Act (1967-04-30) and many areas did not "
                "observe it. Verify local practice; pass dst=False for standard time.")
        else:
            out.append(
                f"pre-1967 US date: {tzname} reflects its principal city; local "
                "practice (DST, and in some areas the standard zone itself) may differ.")
    elif derived:
        out.append(
            f"pre-1970 date: zone {tzname} was derived from coordinates; tzdata only "
            "guarantees accuracy from 1970, earlier rules follow the zone's principal "
            "city. Verify local civil time for this place and date.")
    return out
