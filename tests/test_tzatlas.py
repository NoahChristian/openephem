from datetime import date, datetime

import pytest

from openephem import tzatlas as ta

SQUARE = ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0))


def _rule(**kw):
    base = dict(name="r", start=date(1950, 1, 1), end=date(1960, 1, 1),
                action="standard", source="fixture", polygon=SQUARE)
    base.update(kw)
    return ta.AtlasRule(**base)


def test_polygon_contains():
    r = _rule()
    assert r.contains(5, 5)
    assert r.contains(0, 5)          # boundary counts as inside
    assert not r.contains(11, 5)
    assert not r.contains(5, -1)


def test_concave_polygon():
    # L-shape: notch at top-right
    poly = ((0, 0), (0, 10), (5, 10), (5, 5), (10, 5), (10, 0))
    r = _rule(polygon=poly)
    assert r.contains(2, 8)
    assert r.contains(8, 2)
    assert not r.contains(8, 8)


def test_bbox_and_dates():
    r = _rule(polygon=None, bbox=(0, 0, 10, 10))
    assert r.applies(5, 5, date(1955, 6, 1))
    assert not r.applies(5, 5, date(1960, 1, 1))   # end exclusive
    assert r.applies(5, 5, date(1950, 1, 1))       # start inclusive


def test_match_first_wins_and_datetime():
    a = _rule(name="a")
    b = _rule(name="b")
    assert ta.match([a, b], 5, 5, datetime(1955, 1, 1, 12)).name == "a"
    assert ta.match([a, b], 50, 5, date(1955, 1, 1)) is None
    assert ta.match(None, 5, 5, date(1955, 1, 1)) is None


@pytest.mark.parametrize("kw", [
    dict(polygon=None),                                   # no region
    dict(bbox=(0, 0, 1, 1)),                              # both regions
    dict(polygon=((0, 0), (1, 1))),                       # degenerate polygon
    dict(source="  "),                                    # unsourced
    dict(end=date(1940, 1, 1)),                           # inverted range
    dict(action="offset"),                                # missing offset
    dict(action="zone"),                                  # missing zone
    dict(action="bogus"),
])
def test_validation(kw):
    with pytest.raises(ValueError):
        _rule(**kw)


def test_is_us_zone():
    assert ta.is_us_zone("America/Chicago")
    assert ta.is_us_zone("America/Indiana/Knox")
    assert not ta.is_us_zone("America/Toronto")


def test_principal_city_warnings():
    d = date(1955, 7, 15)
    w = ta.principal_city_warnings("America/Chicago", d, dst_hours=1.0, derived=False)
    assert w and "dst=False" in w[0]
    w = ta.principal_city_warnings("America/Chicago", d, dst_hours=0.0, derived=False)
    assert w and "principal city" in w[0]
    # non-US: only when the zone was derived
    assert ta.principal_city_warnings("Europe/Paris", d, dst_hours=0, derived=False) == []
    assert ta.principal_city_warnings("Europe/Paris", d, dst_hours=0, derived=True)
    # 1967-1969 US: Uniform Time Act in force; generic note only if derived
    assert ta.principal_city_warnings("America/Chicago", date(1968, 7, 1),
                                      dst_hours=1, derived=False) == []
    # post-1970: silent
    assert ta.principal_city_warnings("America/Chicago", date(1990, 7, 1),
                                      dst_hours=1, derived=True) == []
