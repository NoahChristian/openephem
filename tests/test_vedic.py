import pytest
from openephem import vedic

J2000 = 2451545.0


def test_ayanamsa_constants():
    assert abs(vedic.ayanamsa(J2000, "lahiri") - 23.85709) < 1e-3
    assert abs(vedic.ayanamsa(J2000, "fagan_bradley") - 24.74030) < 1e-3
    assert abs(vedic.ayanamsa(J2000, "krishnamurti") - 23.76024) < 1e-3
    assert abs(vedic.ayanamsa(J2000, "raman") - 22.41079) < 1e-3


def test_ayanamsa_precession_rate():
    # ~50.29 arcsec/year: one century should advance ~1.397 deg
    per_century = vedic.ayanamsa(J2000 + 36525.0, "lahiri") - vedic.ayanamsa(J2000, "lahiri")
    assert abs(per_century - 1.39689) < 1e-3


def test_to_sidereal():
    ay = vedic.ayanamsa(J2000, "lahiri")
    assert abs(vedic.to_sidereal(100.0, J2000, "lahiri") - (100.0 - ay) % 360.0) < 1e-9


def test_nakshatra_boundaries():
    assert vedic.nakshatra(0.0)[1] == "Ashwini"
    assert vedic.nakshatra(0.0)[2] == 1
    assert vedic.nakshatra(3.4)[2] == 2                 # pada 2 (3d20 each)
    assert vedic.nakshatra(13.4)[1] == "Bharani"
    assert vedic.nakshatra(359.9)[1] == "Revati"


def test_rashi():
    assert vedic.rashi(0.0) == "Mesha"
    assert vedic.rashi(35.0) == "Vrishabha"
    assert vedic.rashi(359.0) == "Meena"


def test_unknown_ayanamsa():
    with pytest.raises(KeyError):
        vedic.ayanamsa(J2000, "bogus")
