import pytest

from openephem import vedic
from openephem.varga import (
    ESSENTIALS,
    IMPLEMENTED,
    SHODASHAVARGA,
    VARGA_NAMES,
    varga_chart,
    varga_longitude,
    varga_sign,
)


def test_registry_shape():
    assert ESSENTIALS == (1, 2, 3, 9, 10, 12)
    assert len(SHODASHAVARGA) == 16 and SHODASHAVARGA[0] == 1 and SHODASHAVARGA[-1] == 60
    assert set(ESSENTIALS) <= set(VARGA_NAMES) and set(SHODASHAVARGA) == set(VARGA_NAMES)


# a sidereal Moon in Libra (Tulā) at 19.47° → the six essentials, verified by hand
@pytest.mark.parametrize("division,sign_idx", [(1, 6), (2, 3), (3, 10), (9, 11), (10, 0), (12, 1)])
def test_moon_libra_essentials(division, sign_idx):
    assert varga_sign(199.47, division) == sign_idx


def test_d1_is_the_rashi():
    for lon in (0.0, 45.0, 123.4, 359.9):
        assert varga_sign(lon, 1) == int(lon // 30)


def test_d2_hora_is_only_cancer_or_leo():
    for lon in range(0, 360, 5):
        assert varga_sign(float(lon), 2) in (3, 4)     # Karka / Simha


def test_d9_matches_movable_fixed_dual_rule():
    assert varga_sign(0.0, 9) == 0        # Aries (movable) → from itself
    assert varga_sign(30.0, 9) == 9       # Taurus (fixed) → 9th from it (Capricorn)
    assert varga_sign(60.0, 9) == 6       # Gemini (dual) → 5th from it (Libra)
    assert varga_sign(29.9, 9) == 8       # last navāṃśa of Aries → Sagittarius


def test_full_shodashavarga_implemented():
    assert IMPLEMENTED == SHODASHAVARGA and len(IMPLEMENTED) == 16
    for d in SHODASHAVARGA:                # every division yields a valid sign across the zodiac
        for lon in range(0, 360, 13):
            assert 0 <= varga_sign(float(lon), d) < 12


# Aries 3° through each of the ten added divisions, verified by hand
@pytest.mark.parametrize("division,sign_idx", [
    (4, 0), (7, 0), (16, 1), (20, 2), (24, 6), (27, 2), (30, 0), (40, 4), (45, 4), (60, 6)])
def test_added_divisions_aries_3deg(division, sign_idx):
    assert varga_sign(3.0, division) == sign_idx


def test_d30_trimshamsha_unequal_segments():
    # odd sign (Aries): Mars/Saturn/Jupiter/Mercury/Venus → Aries/Aquarius/Sag/Gemini/Libra
    assert [varga_sign(x, 30) for x in (3, 7, 15, 20, 27)] == [0, 10, 8, 2, 6]
    # even sign (Taurus, 30-60°): Venus/Mercury/Jupiter/Saturn/Mars → Taurus/Virgo/Pisces/Cap/Scorpio
    assert [varga_sign(30 + x, 30) for x in (3, 8, 15, 22, 28)] == [1, 5, 11, 9, 7]


def test_non_standard_division_raises():
    with pytest.raises(ValueError):
        varga_sign(10.0, 5)               # D-5 is not one of the sixteen


def test_varga_longitude_lands_in_the_varga_sign():
    for d in ESSENTIALS:
        vl = varga_longitude(199.47, d)
        assert 0.0 <= vl < 360.0
        assert int(vl // 30) == varga_sign(199.47, d)


def test_varga_chart_remaps_and_tags():
    chart = {"zodiac": "sidereal", "angles": {"asc": 15.0},
             "bodies": {"Moon": {"lon": 199.47, "sign": "Tula",
                                 "nakshatra": {"name": "Swati"}, "deg_in_sign": 19.47},
                        "Sun": {"lon": 256.5, "sign": "Dhanu"}}}
    vc = varga_chart(chart, 9)
    assert vc["varga"] == {"division": 9, "name": VARGA_NAMES[9]}
    moon = vc["bodies"]["Moon"]
    assert int(moon["lon"] // 30) == varga_sign(199.47, 9)
    assert moon["sign"] == vedic.rashi(moon["lon"])
    assert "nakshatra" not in moon and "deg_in_sign" not in moon   # D-1 notions dropped
    assert int(vc["angles"]["asc"] // 30) == varga_sign(15.0, 9)
    assert chart["bodies"]["Moon"]["lon"] == 199.47                # original untouched (deep copy)
