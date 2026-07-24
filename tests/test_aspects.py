from openephem import aspects


def _first(l1, l2, **kw):
    r = aspects.find_aspects({"A": {"lon": l1}, "B": {"lon": l2}}, **kw)
    return r[0].aspect if r else None


def test_major_aspects():
    assert _first(0, 0) == "conjunction"
    assert _first(0, 180) == "opposition"
    assert _first(0, 120) == "trine"
    assert _first(0, 90) == "square"
    assert _first(0, 60) == "sextile"
    assert _first(0, 45) is None            # semisquare is minor, off by default


def test_minor_toggle():
    assert _first(0, 30, include_minor=True) == "semisextile"
    assert _first(0, 150, include_minor=True) == "quincunx"


def test_luminary_bonus():
    # Sun-Mars square at 8.5 orb: base 7 + luminary bonus 2 = within 9
    r = aspects.find_aspects({"Sun": {"lon": 0.0}, "Mars": {"lon": 98.5}})
    assert r and r[0].aspect == "square"
    # same orb, no luminary -> beyond base orb -> no aspect
    r2 = aspects.find_aspects({"Jupiter": {"lon": 0.0}, "Mars": {"lon": 98.5}})
    assert not r2


def test_applying_separating():
    ap = aspects.find_aspects({"Sun": {"lon": 0.0, "speed": 1.0},
                               "Moon": {"lon": 119.0, "speed": 13.0}})
    assert ap[0].aspect == "trine" and ap[0].applying is True
    sep_ = aspects.find_aspects({"Sun": {"lon": 0.0, "speed": 1.0},
                                 "Moon": {"lon": 121.0, "speed": 13.0}})
    assert sep_[0].aspect == "trine" and sep_[0].applying is False


def test_applying_none_without_speed():
    r = aspects.find_aspects({"A": {"lon": 0.0}, "B": {"lon": 120.0}})
    assert r[0].applying is None


def test_between_cross_chart():
    # personA Venus @0 vs personB Mars @90 -> square; names kept, charts recorded
    a = {"Venus": {"lon": 0.0}}
    b = {"Mars": {"lon": 90.0}, "Sun": {"lon": 200.0}}
    res = aspects.between(a, b)
    sq = [x for x in res if x.aspect == "square"]
    assert sq and sq[0].a == "Venus" and sq[0].b == "Mars"
    assert sq[0].chart_a == "A" and sq[0].chart_b == "B"
    # no within-set pairs: Sun@B is only compared to Venus@A, not to Mars@B
    assert all({x.a, x.b} != {"Mars", "Sun"} for x in res)


def test_between_same_name_stays_distinct():
    res = aspects.between({"Sun": {"lon": 10.0}}, {"Sun": {"lon": 190.0}}, label_a="natal", label_b="transit")
    assert len(res) == 1 and res[0].aspect == "opposition"
    assert res[0].chart_a == "natal" and res[0].chart_b == "transit"


def test_derived_midpoints():
    from openephem import derived
    assert abs(derived.lon_midpoint(350.0, 10.0) - 0.0) < 1e-9      # wraps: near midpoint is 0
    assert abs(derived.lon_midpoint(350.0, 10.0, far=True) - 180.0) < 1e-9
    lat, lon = derived.geo_midpoint((0.0, 0.0), (0.0, 90.0))         # equator, 0 & 90E -> 45E
    assert abs(lat) < 1e-6 and abs(lon - 45.0) < 1e-6
