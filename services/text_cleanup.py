"""Shared prose cleanups for article drafts.

`strip_em_dashes` used to live privately inside the writing agent, so only
LLM-generated drafts got cleaned — hand-written or produce-path drafts slipped
through with em-dashes intact. It lives here now so every path that ships an
article uses the same rule. Em-dashes are a strong "AI-written" tell.
"""

import re


def strip_em_dashes(text: str) -> str:
    """Replace em-dashes (and spaced en-dashes) used as punctuation with a comma.

    "a — b", "a—b", and a spaced "a – b" all become "a, b". Hyphens and numeric
    ranges like "3–5" (no surrounding spaces) are left untouched.
    """
    text = re.sub(r"[ \t]*—[ \t]*", ", ", text)   # em dash, with any inline spaces
    text = re.sub(r"[ \t]+–[ \t]+", ", ", text)    # spaced en dash used as an em dash
    text = re.sub(r"[ \t]+,", ",", text)            # stray space before the new comma
    text = re.sub(r",[ \t]*,", ",", text)           # collapse doubled commas
    return text
