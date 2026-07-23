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
