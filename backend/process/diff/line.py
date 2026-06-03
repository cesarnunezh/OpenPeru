"""
Layer 2 of the hybrid bill-difference pipeline: per-node line diff.

Takes the text inside one matched node from each version and returns a list
of hunks (non-equal opcodes only) suitable for serialization.

Pure, side-effect-free, stdlib only.
"""

from __future__ import annotations

from difflib import SequenceMatcher


def line_diff(a_text: str, b_text: str) -> list[dict]:
    """Compute a line-level diff between two text blocks.

    Returns a list of hunks, each:
        {
            "op": "insert" | "delete" | "replace",
            "a_start": int, "a_end": int,
            "b_start": int, "b_end": int,
            "a_text": "<lines from A>",
            "b_text": "<lines from B>",
        }

    Equal regions are omitted.  `a_text`/`b_text` for an `insert` is empty on
    the A side; symmetrically for `delete` on the B side.
    """
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    matcher = SequenceMatcher(a=a_lines, b=b_lines, autojunk=False)

    hunks: list[dict] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        hunks.append(
            {
                "op": op,
                "a_start": i1,
                "a_end": i2,
                "b_start": j1,
                "b_end": j2,
                "a_text": "\n".join(a_lines[i1:i2]),
                "b_text": "\n".join(b_lines[j1:j2]),
            }
        )
    return hunks
