"""
Render a structured ``compute_bill_difference`` payload to HTML.

Called from the bill-diff route at request time.  Cheap enough on real bills
(milliseconds) that we cache via ETag + ``Cache-Control`` rather than
persisting the markup.  ``RENDERER_VERSION`` is a component of the ETag,
so bumping it invalidates client caches without any backfill.

Pure, side-effect-free, stdlib only.
"""

from __future__ import annotations

from html import escape

# Bump when the emitted HTML / CSS-class contract changes so existing ETags
# no longer match and clients refetch.
RENDERER_VERSION = 1

# Brackets that bind to the *following* token (no space after).
_OPEN_BRACKETS = frozenset("([{¿¡")

# Characters that can act as either an opening or closing quote depending
# on position.  We alternate per-character: the first ``"`` opens, the
# second closes, the third opens again, and so on.
_AMBIGUOUS_QUOTES = frozenset("\"'")


def _join_tokens(tokens: list[str]) -> str:
    """Reassemble tokens into a human-readable string.

    * Closing punctuation/brackets attach to the previous word.
    * Opening brackets (and Spanish ``¿`` / ``¡``) attach to the next word.
    * Straight quotes (``"`` and ``'``) alternate: each occurrence flips
      between opening-role and closing-role.  Within a single hunk this
      reproduces ``"hola"`` correctly; across hunks the alternation may
      start out-of-phase, which is a known limitation.
    * Everything else is space-separated.
    """
    out: list[str] = []
    pending_open = False
    # Per-character "currently inside this quote?" flag.  Keyed so that
    # `"` and `'` track independently.
    inside_quote: dict[str, bool] = {}
    for t in tokens:
        if not t:
            continue
        if t in _OPEN_BRACKETS:
            if out and not pending_open:
                out.append(" ")
            out.append(t)
            pending_open = True
            continue
        if t in _AMBIGUOUS_QUOTES:
            if not inside_quote.get(t, False):
                # Opening role: behaves like an open bracket.
                if out and not pending_open:
                    out.append(" ")
                out.append(t)
                pending_open = True
                inside_quote[t] = True
            else:
                # Closing role: no leading space.
                out.append(t)
                pending_open = False
                inside_quote[t] = False
            continue
        if not t[0].isalnum():
            # Other closing punctuation — no leading space.
            out.append(t)
            pending_open = False
            continue
        if out and not pending_open:
            out.append(" ")
        out.append(t)
        pending_open = False
    return "".join(out).lstrip()


# ── HTML emitters ───────────────────────────────────────────────────────────


# Tags wrapping each kind of run.  Looked up by op.
_RUN_TAGS = {
    "equal": ('<span class="diff-tok-equal">', "</span>"),
    "delete": ('<del class="diff-tok-delete">', "</del>"),
    "insert": ('<ins class="diff-tok-insert">', "</ins>"),
}


def _render_word_diff(word_diff: list[dict]) -> str:
    """Convert ``word_diff`` opcodes into an inline HTML fragment.

    ``replace`` opcodes are expanded into adjacent ``delete`` + ``insert``
    runs.  Spacing between runs is decided by the same token-adjacency
    rules as ``_join_tokens`` (closing punctuation snugs to the previous
    run, opening brackets snug to the next) so a single-punctuation hunk
    doesn't render with stray spaces — e.g. ``hola, mundo → hola; mundo``
    renders as ``hola<del>,</del><ins>;</ins> mundo``, not ``hola , ; mundo``.
    """
    # Expand each opcode into one or two (op, tokens) entries.
    runs: list[tuple[str, list[str]]] = []
    for run in word_diff:
        op = run["op"]
        if op == "equal":
            runs.append(("equal", run.get("a_tokens", [])))
        elif op == "delete":
            runs.append(("delete", run.get("a_tokens", [])))
        elif op == "insert":
            runs.append(("insert", run.get("b_tokens", [])))
        elif op == "replace":
            runs.append(("delete", run.get("a_tokens", [])))
            runs.append(("insert", run.get("b_tokens", [])))

    out: list[str] = []
    prev_last_token: str | None = None
    for op, tokens in runs:
        if not tokens:
            continue
        first = tokens[0]
        # Decide whether a space goes BEFORE this run.
        space_before = (
            prev_last_token is not None
            and prev_last_token not in _OPEN_BRACKETS
            and (first[0].isalnum() or first in _OPEN_BRACKETS)
        )
        if space_before:
            out.append(" ")
        open_tag, close_tag = _RUN_TAGS[op]
        out.append(open_tag + escape(_join_tokens(tokens)) + close_tag)
        prev_last_token = tokens[-1]

    return "".join(out)


def _render_hunk_body(hunk: dict) -> str:
    """Best inline rendering for a hunk.

    Prefers the word-level diff; falls back to whole-text spans when
    ``word_diff`` is missing.
    """
    word_diff = hunk.get("word_diff") or []
    if word_diff:
        return _render_word_diff(word_diff)

    op = hunk["op"]
    a_text = hunk.get("a_text", "")
    b_text = hunk.get("b_text", "")
    if op == "insert":
        return f'<ins class="diff-tok-insert">{escape(b_text)}</ins>'
    if op == "delete":
        return f'<del class="diff-tok-delete">{escape(a_text)}</del>'
    return (
        f'<del class="diff-tok-delete">{escape(a_text)}</del> '
        f'<ins class="diff-tok-insert">{escape(b_text)}</ins>'
    )


def _render_hunk(hunk: dict) -> str:
    op = hunk["op"]
    a_range = f"{hunk.get('a_start', 0)}–{hunk.get('a_end', 0)}"
    b_range = f"{hunk.get('b_start', 0)}–{hunk.get('b_end', 0)}"
    return (
        f'<div class="diff-hunk diff-hunk-{escape(op)}">'
        f'<div class="diff-hunk-header">'
        f'<span class="diff-hunk-op">{escape(op)}</span>'
        f'<span class="diff-hunk-range">lines a[{escape(a_range)}] → b[{escape(b_range)}]</span>'
        f"</div>"
        f'<p class="diff-hunk-body">{_render_hunk_body(hunk)}</p>'
        f"</div>"
    )


def _render_node(node: dict) -> str:
    status = node.get("status", "matched")
    hunks_html = "".join(_render_hunk(h) for h in node.get("hunks") or [])

    return (
        f'<section class="diff-node diff-node-{escape(status)}">{hunks_html}</section>'
    )


def _render_summary(summary: dict) -> str:
    pills = [
        f'<span class="diff-summary-pill">{summary.get("nodes_total", 0)} sections</span>',
        f'<span class="diff-summary-pill diff-summary-changed">'
        f"{summary.get('nodes_changed', 0)} changed</span>",
    ]
    if summary.get("nodes_inserted"):
        pills.append(
            f'<span class="diff-summary-pill diff-summary-inserted">'
            f"+{summary['nodes_inserted']} added</span>"
        )
    if summary.get("nodes_deleted"):
        pills.append(
            f'<span class="diff-summary-pill diff-summary-deleted">'
            f"−{summary['nodes_deleted']} removed</span>"
        )
    if summary.get("nodes_renamed"):
        pills.append(
            f'<span class="diff-summary-pill diff-summary-renamed">'
            f"{summary['nodes_renamed']} renumbered</span>"
        )
    return f'<div class="diff-summary">{"".join(pills)}</div>'


# ── Public entry point ──────────────────────────────────────────────────────


def render_payload_html(payload: dict | None) -> str | None:
    """Render a ``compute_bill_difference`` payload as an HTML fragment.

    Returns ``None`` when the payload is missing or shaped wrong, so the
    caller can persist ``NULL`` and let the template fall back.

    The returned string is an HTML fragment (no ``<html>`` / ``<body>``),
    safe to drop into an existing template with the ``| safe`` filter.  All
    text drawn from the payload is HTML-escaped.
    """
    if not isinstance(payload, dict) or "nodes" not in payload:
        return None

    rendered_nodes = []
    for node in payload.get("nodes", []):
        hunks = node.get("hunks") or []
        if not hunks and node.get("status") == "matched":
            # Skip clean-matched nodes — no information to show.
            continue
        rendered_nodes.append(_render_node(node))

    if not rendered_nodes:
        body = '<p class="diff-status diff-status-equal">No structural changes detected.</p>'
    else:
        body = "".join(rendered_nodes)

    return (
        f'<div class="diff-rendered" data-renderer-version="{RENDERER_VERSION}">'
        f"{body}"
        f"</div>"
    )
