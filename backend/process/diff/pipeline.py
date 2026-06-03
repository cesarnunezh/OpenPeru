"""
Compose the three-layer hybrid diff (structural → line → word).

`compute_bill_difference` keeps the same outer shape used elsewhere in the
codebase: ``{"type": <one of UNAVAILABLE|FIRST_VERSION|NO_CHANGE|INCOMPARABLE|MODIFIED>, "content": <payload or None>}``.

For ``modified`` results, ``content`` is now a structured payload — see
``_build_payload`` for the schema — rather than a flat list of ndiff lines.
The payload is JSON-serializable and intended for the ``difference_content``
column on ``bill_differences``.
"""

from __future__ import annotations

import re
import unicodedata

from backend.process.diff.line import line_diff
from backend.process.diff.structural import (
    Alignment,
    HEADER_LOOKAHEAD_PATTERN,
    align_nodes,
    parse_structure,
)
from backend.process.diff.word import word_diff

# Documents whose sizes differ by more than this factor are flagged as
# incomparable rather than producing a noisy diff (e.g. full dictamen vs
# a short amendment letter).
_MAX_SIZE_RATIO = 10.0

# Bump when the parser/aligner/diff output schema changes meaningfully so
# the orchestrator can decide to recompute.  Stored alongside the payload.
PARSER_VERSION = 1


# ── Normalization ───────────────────────────────────────────────────────────


# Allow leading whitespace before the header — OCR output frequently
# indents section anchors, and we still want the structural parser to
# see those lines as boundaries.
_REFLOW_RE = re.compile(
    rf"(?<!\n)\n(?!\n)(?!\s*{HEADER_LOOKAHEAD_PATTERN})",
    flags=re.IGNORECASE,
)


def _normalize_for_diff(text: str) -> str:
    """Collapse OCR line-reflow noise and standardize typography.

    Applied to both sides of every diff so we don't flag pure formatting
    artifacts.

    Steps (in order):
      1. Unicode NFC, to compose precomposed accented characters without the
         compatibility decompositions (``º → o``, ``½ → 1/2``, superscripts →
         digits) that NFKC would do — those are content, not noise.
      2. Standardize fancy quotes / dashes to ASCII equivalents.
      3. Collapse runs of spaces/tabs.
      4. Join mid-sentence single newlines — but **not** when the next line
         starts with a structural header (``Artículo``, ``TÍTULO``, etc.),
         so the structural parser still sees the boundary.  Genuine
         paragraph breaks (two or more newlines) are always preserved.
      5. Strip per-line, drop empty lines.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = _REFLOW_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# ── Public API ──────────────────────────────────────────────────────────────


def compute_bill_difference(old_text: str | None, new_text: str | None) -> dict:
    """Compare two versions of a bill body using the hybrid three-layer diff.

    Returns ``{"type": <kind>, "content": <payload | None>}``.

    ``type`` is one of:
      - ``"unavailable"``  — new text missing (no extraction yet); cannot diff
      - ``"first_version"`` — no prior version
      - ``"no_change"``    — texts equal after normalization
      - ``"incomparable"`` — size ratio exceeded; probably mismatched documents
      - ``"modified"``     — structured payload returned

    ``content`` for ``modified`` is documented in ``_build_payload``.
    """
    if new_text is None:
        # Either no BillText row for this step yet, or we explicitly have no
        # new side to compare. Either way: no diff. Without this, a prior
        # text + missing new text would render as "everything deleted".
        return {"type": "unavailable", "content": None}
    if old_text is None:
        return {"type": "first_version", "content": None}

    lo, hi = sorted([len(old_text), len(new_text)])
    # One side empty, the other not: probably failed OCR / extraction —
    # don't materialize an O(N) deletion or insertion payload.
    if lo == 0 and hi > 0:
        return {"type": "incomparable", "content": None}
    if lo > 0 and hi / lo > _MAX_SIZE_RATIO:
        return {"type": "incomparable", "content": None}

    if old_text == new_text:
        return {"type": "no_change", "content": None}

    old_norm = _normalize_for_diff(old_text)
    new_norm = _normalize_for_diff(new_text)

    if old_norm == new_norm:
        return {"type": "no_change", "content": None}

    return {"type": "modified", "content": _build_payload(old_norm, new_norm)}


# ── Composition ─────────────────────────────────────────────────────────────


def _build_payload(old_norm: str, new_norm: str) -> dict:
    """Run the three layers and assemble the JSON-serializable payload.

    Schema (all keys present, lists may be empty):

    .. code-block::

        {
          "parser_version": int,
          "summary": {
            "nodes_total": int,
            "nodes_changed": int,
            "nodes_inserted": int,
            "nodes_deleted": int,
            "nodes_renamed": int,    # matched by fingerprint/similarity
          },
          "nodes": [
            {
              "node_id": "articulo_5",
              "kind": "articulo",
              "status": "matched" | "inserted" | "deleted",
              "match_strategy": "id" | "fingerprint" | "similarity" | "deleted" | "inserted",
              "a_label": "...",                    # may be null for inserts
              "b_label": "...",                    # may be null for deletes
              "hunks": [
                {
                  "op": "insert" | "delete" | "replace",
                  "a_start": int, "a_end": int,
                  "b_start": int, "b_end": int,
                  "a_text": "...", "b_text": "...",
                  "word_diff": [
                    {"op": "equal" | "insert" | "delete" | "replace",
                     "a_tokens": [...], "b_tokens": [...]}
                  ]
                }
              ]
            },
            ...
          ]
        }
    """
    a_nodes = parse_structure(old_norm)
    b_nodes = parse_structure(new_norm)
    alignments = align_nodes(a_nodes, b_nodes)

    nodes_payload: list[dict] = []
    renamed = 0
    for align in alignments:
        node_block = _build_node_block(align)
        if align.status in {"fingerprint", "similarity"}:
            renamed += 1
        nodes_payload.append(node_block)

    changed = sum(1 for n in nodes_payload if n["hunks"] or n["status"] != "matched")
    inserted = sum(1 for n in nodes_payload if n["status"] == "inserted")
    deleted = sum(1 for n in nodes_payload if n["status"] == "deleted")

    return {
        "parser_version": PARSER_VERSION,
        "summary": {
            "nodes_total": len(nodes_payload),
            "nodes_changed": changed,
            "nodes_inserted": inserted,
            "nodes_deleted": deleted,
            "nodes_renamed": renamed,
        },
        "nodes": nodes_payload,
    }


def _build_node_block(align: Alignment) -> dict:
    a, b = align.a, align.b
    if a is None and b is not None:
        status = "inserted"
        hunks = _hunks_for(a_text="", b_text=b.text)
    elif b is None and a is not None:
        status = "deleted"
        hunks = _hunks_for(a_text=a.text, b_text="")
    else:
        assert a is not None and b is not None
        status = "matched"
        hunks = _hunks_for(a_text=a.text, b_text=b.text)

    return {
        "node_id": (b or a).node_id,  # type: ignore[union-attr]
        "kind": (b or a).kind,  # type: ignore[union-attr]
        "status": status,
        "match_strategy": align.status,
        "a_label": a.label if a else None,
        "b_label": b.label if b else None,
        "hunks": hunks,
    }


def _hunks_for(*, a_text: str, b_text: str) -> list[dict]:
    hunks = line_diff(a_text, b_text)
    for h in hunks:
        h["word_diff"] = word_diff(h["a_text"], h["b_text"])
    return hunks
