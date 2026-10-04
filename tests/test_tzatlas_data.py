"""Schema + loader tests for the bundled tzatlas rule data (openephem/data/tzatlas/).

The bundled ruleset may be empty (rules are added only from vetted primary sources), so the
pipeline is proven here with inline example rules; whatever IS bundled is validated for free.
"""
from datetime import date

import pytest

from openephem import tzatlas as ta


def _have_tzdata():
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("America/Chicago")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Loader / round-trip (inline examples — independent of what is bundled)
# --------------------------------------------------------------------------- #
def test_load_rules_from_list_and_wrapper():
    rule = {"name": "ex", "start": "1950-01-01", "end": "1960-01-01",
            "action": "standard", "bbox": [0, 0, 10, 10], "source": "fixture"}
    assert len(ta.load_rules([rule])) == 1
    assert len(ta.load_rules({"rules": [rule]})) == 1          # {"rules": [...]} wrapper
    assert ta.load_rules('{"rules": []}') == []               # JSON string
    assert ta.load_rules("[]") == []


def test_load_rules_builds_every_field():
    rule = {
        "name": "on Mountain", "start": "1950-01-01", "end": "1960-01-01",
        "action": "zone", "zone": "America/Denver",
        "polygon": [[38.0, -99.0], [39.0, -99.0], [39.0, -98.0]],
        "source": "ICC order", "source_url": "https://example.gov/fr",
        "note": "n", "tags": ["us-zone-boundary"],
    }
    (r,) = ta.load_rules([rule])
    assert r.action == "zone" and r.zone == "America/Denver"
    assert r.polygon == ((38.0, -99.0), (39.0, -99.0), (39.0, -98.0))
    assert r.tags == ("us-zone-boundary",)
    assert "ICC order" in r.source and "example.gov" in r.source   # source_url appended


def test_load_rules_offset_and_dates():
    (r,) = ta.load_rules([{"name": "o", "start": "1946-01-01", "end": "1967-04-30",
                           "action": "offset", "offset_hours": -6.0,
                           "bbox": [36.9, -102.1, 40.0, -94.6], "source": "fixture"}])
    assert r.offset_hours == -6.0
    assert r.start == date(1946, 1, 1) and r.end == date(1967, 4, 30)


def test_load_rules_rejects_unsourced():
    with pytest.raises(ValueError):
        ta.load_rules([{"name": "x", "start": "1950-01-01", "end": "1960-01-01",
                        "action": "standard", "bbox": [0, 0, 1, 1], "source": "  "}])


# --------------------------------------------------------------------------- #
# Bundled ruleset (may be empty)
# --------------------------------------------------------------------------- #
def test_bundled_rules_are_valid_and_sourced():
    rules = ta.bundled_rules()
    assert isinstance(rules, list)
    names = [r.name for r in rules]
    assert len(names) == len(set(names)), "bundled rule names must be unique"
    for r in rules:
        assert isinstance(r, ta.AtlasRule)       # construction already validated it
        assert r.source.strip()                  # primary citation present
        assert (r.bbox is None) != (r.polygon is None)


def _sample_points(r):
    """Centroid + interior-ish corners of a rule's region (pulled slightly inward)."""
    if r.bbox is not None:
        a, b, c, d = r.bbox          # min_lat, min_lon, max_lat, max_lon
        dlat, dlon = (c - a) * 0.05, (d - b) * 0.05
        return [((a + c) / 2, (b + d) / 2), (a + dlat, b + dlon), (a + dlat, d - dlon),
                (c - dlat, b + dlon), (c - dlat, d - dlon)]
    assert r.polygon is not None
    return [(sum(p[0] for p in r.polygon) / len(r.polygon),
             sum(p[1] for p in r.polygon) / len(r.polygon))]


@pytest.mark.skipif(not _have_tzdata(), reason="IANA tzdata not available")
def test_bundled_rules_are_additive():
    """Every bundled rule must CHANGE the offset default tzdata would give for at least one
    sampled point AND date in its window — a rule that merely echoes tzdata everywhere is
    redundant (and the well-handled cases belong in tzdata, not here). Region rules are sampled
    at several points and in both winter and summer, since a correction may only show in part of
    the region or season (e.g. a standard-zone fix shows in winter; a no-DST fix shows in summer)."""
    from openephem.timeplace import resolve
    mid_year = None
    for r in ta.bundled_rules():
        mid_year = (r.start.year + (r.end.year - 1)) // 2
        dates = [(r.start.year, r.start.month, r.start.day), (mid_year, 7, 15),
                 (mid_year, 1, 15)]
        additive = False
        for lat, lon in _sample_points(r):
            for ymd in dates:
                base = resolve(date=ymd, time=(12, 0), lat=lat, lon=lon)
                over = resolve(date=ymd, time=(12, 0), lat=lat, lon=lon, atlas=[r])
                if over.offset_hours != base.offset_hours:
                    additive = True
                    break
            if additive:
                break
        assert additive, f"bundled rule {r.name!r} is not additive anywhere in its region/window"
