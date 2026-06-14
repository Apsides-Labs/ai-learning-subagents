from services.text_cleanup import strip_em_dashes


def test_em_dash_space_both_sides():
    assert strip_em_dashes("learning — which") == "learning, which"


def test_em_dash_no_spaces():
    assert strip_em_dashes("learning—which") == "learning, which"


def test_em_dash_space_before_only():
    assert strip_em_dashes("learning —which") == "learning, which"


def test_em_dash_multiple():
    assert strip_em_dashes("fast — effective — proven") == "fast, effective, proven"


def test_no_em_dash_unchanged():
    assert strip_em_dashes("no emdash here") == "no emdash here"


def test_spaced_en_dash_becomes_comma():
    assert strip_em_dashes("lessons and quizzes – from one prompt") == "lessons and quizzes, from one prompt"


def test_numeric_range_en_dash_preserved():
    # No surrounding spaces => it's a range, not punctuation. Leave it alone.
    assert strip_em_dashes("write 3–5 tests") == "write 3–5 tests"


def test_hyphen_preserved():
    assert strip_em_dashes("a well-described subagent") == "a well-described subagent"


def test_no_doubled_comma_when_dash_follows_text():
    # "model — what" should not produce a stray double comma or space.
    assert strip_em_dashes("the model — what changes") == "the model, what changes"
