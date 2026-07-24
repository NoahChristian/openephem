from openephem import bodies, available_bodies


def test_master_list():
    names = available_bodies()
    assert len(names) > 40
    for n in ("Sun", "Ceres", "Eris", "Sedna", "Hygeia", "Vertex",
              "PartOfFortune", "Cupido", "TransPluto", "WhiteMoon"):
        assert n in names, n


def test_aliases_and_canonical():
    assert bodies.canonical("AC") == "Ascendant"
    assert bodies.canonical("PoF") == "PartOfFortune"
    assert bodies.canonical("Hygiea") == "Hygeia"          # spelling variant
    assert bodies.canonical("Ketu") == "SouthNode"
    assert bodies.canonical("NotAThing") is None
    assert bodies.get("dc").name == "Descendant"


def test_filters():
    ast = available_bodies(kind="asteroid")
    assert {"Ceres", "Hygeia", "Astraea"} <= set(ast) and "Sun" not in ast
    pts = available_bodies(engine="point")
    assert {"Vertex", "Descendant", "EastPoint"} <= set(pts)
    pending = available_bodies(implemented=False)
    assert "PolarAscendant" in pending                         # awaiting definition
    assert "Sun" not in pending and "Cupido" not in pending    # Uranians now computed
    impl = available_bodies(implemented=True)
    assert {"Cupido", "TransPluto", "Vulcan", "WhiteMoon", "CoAscendant",
            "PartOfFortune", "Sedna"} <= set(impl)
    assert "PolarAscendant" not in impl


def test_kernels_declared_for_asteroids():
    for n in available_bodies(engine="asteroid"):
        assert bodies.get(n).kernel, f"{n} missing kernel filename"
