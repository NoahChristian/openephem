import openephem


def test_version():
    assert openephem.__version__


def test_public_api():
    for name in ("assemble", "render_svg", "resolve", "houses", "aspects",
                 "vedic", "chart", "wheel", "timeplace", "service",
                 "planets_skyfield", "asteroids_skyfield", "fixed_stars",
                 "fetch_kernels"):
        assert hasattr(openephem, name), name
