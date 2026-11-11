from wtl.candidates import codes_in


def test_short_parameter_names():
    # Talk:The Holocaust, 2026-11-11
    assert codes_in("{{Contentious topics/talk notice|t=apl|t2=ee}}") == {"APL", "EE"}


def test_long_and_positional_forms():
    assert codes_in("{{Contentious topics/talk notice|topic=e-e}}") == {"EE"}
    assert codes_in("{{Contentious topics/talk notice|e-e}}") == {"EE"}


def test_other_parameters_ignored():
    assert codes_in("{{Contentious topics/talk notice|style=long|small=yes}}") == set()
