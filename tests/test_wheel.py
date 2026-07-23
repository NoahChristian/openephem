import re
import xml.etree.ElementTree as ET
import pytest
from openephem import wheel, houses


def _mock_chart():
    h = houses.houses_from_jd(2451545.0, 40.0, -75.0, "Placidus")
    return {
        "angles": {"asc": h.asc, "mc": h.mc, "vertex": h.vertex,
                   "east_point": h.east_point},
        "cusps": h.cusps,
        "bodies": {"Sun": {"lon": 50.0, "retro": False},
                   "Moon": {"lon": 230.0, "retro": True}},
        "aspects": [{"a": "Sun", "b": "Moon", "aspect": "opposition", "orb": 0.5}],
    }


def test_svg_wellformed():
    s = wheel.render_svg(_mock_chart(), title="test")
    assert s.lstrip().startswith("<svg")
    assert s.rstrip().endswith("</svg>")
    assert "planet" in s and "aspect" in s and "sign" in s


def test_svg_no_nan_coordinates():
    s = wheel.render_svg(_mock_chart())
    # 'nan' appears in 'dominant-baseline'; only flag it inside numeric attributes
    assert not re.search(r'"[-\d.]*nan[-\d.]*"', s.lower())


@pytest.mark.parametrize("theme", ["light", "dark", "auto"])
def test_svg_wellformed_xml_all_themes(theme):
    # every theme must emit well-formed XML (dark once emitted an unbalanced <style>)
    ET.fromstring(wheel.render_svg(_mock_chart(), theme=theme))


def test_svg_without_houses():
    # unknown-time chart (no angles/cusps) still renders a zodiac ring
    chart = {"angles": None, "cusps": None,
             "bodies": {"Sun": {"lon": 10.0}}, "aspects": []}
    s = wheel.render_svg(chart)
    assert s.lstrip().startswith("<svg")
