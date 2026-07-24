import openephem


def test_version():
    assert openephem.__version__


def test_public_api():
    for name in ("assemble", "resolve", "houses", "aspects", "vedic", "chart",
                 "schema", "timeplace", "service", "planets_skyfield",
                 "asteroids_skyfield", "fixed_stars", "fetch_kernels"):
        assert hasattr(openephem, name), name


def test_rendering_is_not_in_the_calc_core():
    # SVG rendering lives in the separate `ephemvis` package, not openephem.
    assert not hasattr(openephem, "render_svg")
    assert not hasattr(openephem, "wheel")
