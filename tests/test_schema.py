from openephem import schema


def test_validate_ok():
    assert schema.validate({"bodies": {"Sun": {"lon": 10.0}}}) == []


def test_validate_problems():
    assert schema.validate("not a dict")                                   # non-dict
    assert any("non-empty" in p for p in schema.validate({}))              # missing bodies
    assert any("missing 'lon'" in p for p in schema.validate({"bodies": {"Sun": {}}}))
    assert any("cusps" in p for p in schema.validate(
        {"bodies": {"Sun": {"lon": 1}}, "cusps": [1, 2]}))                 # wrong-length cusps
    assert any("aspect" in p for p in schema.validate(
        {"bodies": {"Sun": {"lon": 1}}, "aspects": [{"a": "x"}]}))         # incomplete aspect


def test_module_surface():
    assert isinstance(schema.SCHEMA_VERSION, str)
    assert "conjunction" in schema.ASPECTS
