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


@pytest.mark.skipif(not _have_tzdata(), reason="IANA tzdata not available")
def test_bundled_rules_are_additive():
    """Every bundled rule must CHANGE the offset default tzdata would give for at least one
    sampled point/date in its window — a rule that merely echoes tzdata is redundant (and the
    well-handled cases belong in tzdata, not here)."""
    from openephem.timeplace import resolve
    for r in ta.bundled_rules():
        if r.bbox is not None:
            lat = (r.bbox[0] + r.bbox[2]) / 2
            lon = (r.bbox[1] + r.bbox[3]) / 2
        else:
            assert r.polygon is not None
            lat = sum(p[0] for p in r.polygon) / len(r.polygon)
            lon = sum(p[1] for p in r.polygon) / len(r.polygon)
        when = r.start
        base = resolve(date=(when.year, when.month, when.day), time=(12, 0),
                       lat=lat, lon=lon)
        over = resolve(date=(when.year, when.month, when.day), time=(12, 0),
                       lat=lat, lon=lon, atlas=[r])
        assert over.offset_hours != base.offset_hours or over.atlas_rule == r.name, (
            f"bundled rule {r.name!r} is not additive at its own sample point")
