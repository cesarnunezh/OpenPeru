"""
Layer 3 of the hybrid bill-difference pipeline: per-hunk word diff.

Tokenizes each side and runs difflib over the token lists so the UI can
highlight only the words that changed inside a line, not the whole line.

Pure, side-effect-free, stdlib only.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Match a word OR a single non-space, non-word character.  Whitespace is
# discarded.  This keeps punctuation as its own token (so a comma change is
# one token swap, not a partial-word edit).
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def word_diff(a_text: str, b_text: str) -> list[dict]:
    """Compute a token-level diff between two strings.

    Returns a list of runs covering both sides:
        {
            "op": "equal" | "insert" | "delete" | "replace",
            "a_tokens": [...], "b_tokens": [...],
        }

    `equal` runs are kept so the renderer can reconstruct the line with
    inline highlights without needing the original text.
    """
    a_tokens = _tokenize(a_text)
    b_tokens = _tokenize(b_text)
    matcher = SequenceMatcher(a=a_tokens, b=b_tokens, autojunk=False)
    return [
        {
            "op": op,
            "a_tokens": a_tokens[i1:i2],
            "b_tokens": b_tokens[j1:j2],
        }
        for op, i1, i2, j1, j2 in matcher.get_opcodes()
    ]
