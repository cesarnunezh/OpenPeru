from app.diff_render import (
    RENDERER_VERSION,
    _join_tokens,
    render_payload_html,
)


# ── token joining ───────────────────────────────────────────────────────────


def test_join_tokens_basic():
    assert _join_tokens(["hola", "mundo"]) == "hola mundo"


def test_join_tokens_attaches_closing_punctuation():
    assert _join_tokens(["hola", ",", "mundo", "."]) == "hola, mundo."


def test_join_tokens_attaches_opening_brackets_to_next():
    assert _join_tokens(["ver", "(", "Artículo", "5", ")"]) == "ver (Artículo 5)"


def test_join_tokens_handles_spanish_inverted_marks():
    assert _join_tokens(["¿", "cierto", "?"]) == "¿cierto?"


def test_join_tokens_alternates_straight_quotes():
    # Regression: the previous implementation treated `"` as plain closing
    # punctuation, so `"hola"` rendered as `" hola"` with a stray inner space.
    assert _join_tokens(['"', "hola", '"']) == '"hola"'
    assert _join_tokens(["dice", '"', "hola", '"', "ahora"]) == 'dice "hola" ahora'


def test_join_tokens_alternates_apostrophes_independently_from_quotes():
    # Two independent alternation counters — a `'` doesn't reset the `"` state.
    out = _join_tokens(["el", '"', "alma", "'", "del", "'", "lugar", '"'])
    # Acceptable shape: both quote pairs wrap their contents cleanly.
    assert '"alma' in out
    assert 'lugar"' in out


# ── render_payload_html ─────────────────────────────────────────────────────


def _payload(nodes):
    return {
        "parser_version": 1,
        "summary": {
            "nodes_total": len(nodes),
            "nodes_changed": sum(
                1 for n in nodes if n.get("hunks") or n.get("status") != "matched"
            ),
            "nodes_inserted": sum(1 for n in nodes if n.get("status") == "inserted"),
            "nodes_deleted": sum(1 for n in nodes if n.get("status") == "deleted"),
            "nodes_renamed": 0,
        },
        "nodes": nodes,
    }


def test_render_returns_none_for_bad_input():
    assert render_payload_html(None) is None
    assert render_payload_html([]) is None
    assert render_payload_html({"unrelated": "shape"}) is None


def test_render_skips_clean_matched_nodes_without_summary():
    html = render_payload_html(
        _payload(
            [
                {
                    "node_id": "articulo_1",
                    "kind": "articulo",
                    "status": "matched",
                    "match_strategy": "id",
                    "a_label": "Artículo 1.-",
                    "b_label": "Artículo 1.-",
                    "hunks": [],
                }
            ]
        )
    )
    assert html is not None
    assert "diff-summary" not in html
    assert "No structural changes detected." in html
    assert "diff-node" not in html


def test_render_emits_word_diff_with_escaped_text():
    html = render_payload_html(
        _payload(
            [
                {
                    "node_id": "articulo_1",
                    "kind": "articulo",
                    "status": "matched",
                    "match_strategy": "id",
                    "a_label": "Artículo 1.-",
                    "b_label": "Artículo 1.-",
                    "hunks": [
                        {
                            "op": "replace",
                            "a_start": 0,
                            "a_end": 1,
                            "b_start": 0,
                            "b_end": 1,
                            "a_text": "INTERES",
                            "b_text": "INTERÉS",
                            "word_diff": [
                                {
                                    "op": "replace",
                                    "a_tokens": ["INTERES"],
                                    "b_tokens": ["INTERÉS"],
                                }
                            ],
                        }
                    ],
                }
            ]
        )
    )
    assert html is not None
    assert '<del class="diff-tok-delete">INTERES</del>' in html
    assert '<ins class="diff-tok-insert">INTERÉS</ins>' in html
    assert f'data-renderer-version="{RENDERER_VERSION}"' in html


def test_render_escapes_html_in_user_text():
    html = render_payload_html(
        _payload(
            [
                {
                    "node_id": "articulo_1",
                    "kind": "articulo",
                    "status": "matched",
                    "match_strategy": "id",
                    "a_label": "Artículo 1.-",
                    "b_label": "<script>alert(1)</script>",
                    "hunks": [
                        {
                            "op": "replace",
                            "a_start": 0,
                            "a_end": 1,
                            "b_start": 0,
                            "b_end": 1,
                            "a_text": "x",
                            "b_text": "<b>y</b>",
                            "word_diff": [
                                {
                                    "op": "replace",
                                    "a_tokens": ["<b>x</b>"],
                                    "b_tokens": ["<b>y</b>"],
                                }
                            ],
                        }
                    ],
                }
            ]
        )
    )
    assert "<script>" not in html
    assert "&lt;b&gt;y&lt;/b&gt;" in html


def test_render_handles_inserted_node():
    html = render_payload_html(
        _payload(
            [
                {
                    "node_id": "articulo_3",
                    "kind": "articulo",
                    "status": "inserted",
                    "match_strategy": "inserted",
                    "a_label": None,
                    "b_label": "Artículo 3.- Nuevo",
                    "hunks": [
                        {
                            "op": "insert",
                            "a_start": 0,
                            "a_end": 0,
                            "b_start": 0,
                            "b_end": 2,
                            "a_text": "",
                            "b_text": "Artículo 3.- Nuevo\ncontenido",
                            "word_diff": [
                                {
                                    "op": "insert",
                                    "a_tokens": [],
                                    "b_tokens": ["Artículo", "3", ".", "-", "Nuevo"],
                                }
                            ],
                        }
                    ],
                }
            ]
        )
    )
    assert "diff-node-inserted" in html
    assert "diff-node-badge-inserted" not in html
    assert "Artículo 3.- Nuevo" in html


def test_render_punctuation_run_has_no_stray_space():
    # Regression: the renderer used `" ".join(parts)` which inserted a
    # space between every emitted run.  A single-punctuation change like
    # ``hola, mundo → hola; mundo`` rendered as ``hola , ; mundo``.
    from app.diff_render import _render_word_diff

    word_diff = [
        {"op": "equal", "a_tokens": ["hola"], "b_tokens": ["hola"]},
        {"op": "replace", "a_tokens": [","], "b_tokens": [";"]},
        {"op": "equal", "a_tokens": ["mundo"], "b_tokens": ["mundo"]},
    ]
    html = _render_word_diff(word_diff)
    # No stray spaces before the comma or semicolon.
    assert "hola</span><del" in html
    assert "</del><ins" in html
    # The space before "mundo" is fine — it's a normal word boundary.
    assert "</ins> <span" in html
    # And the wrong rendering must be absent.
    assert "hola , " not in html
    assert " , " not in html


def test_render_falls_back_when_word_diff_missing():
    html = render_payload_html(
        _payload(
            [
                {
                    "node_id": "articulo_2",
                    "kind": "articulo",
                    "status": "matched",
                    "match_strategy": "id",
                    "a_label": "Artículo 2.-",
                    "b_label": "Artículo 2.-",
                    "hunks": [
                        {
                            "op": "replace",
                            "a_start": 0,
                            "a_end": 1,
                            "b_start": 0,
                            "b_end": 1,
                            "a_text": "viejo",
                            "b_text": "nuevo",
                            # no word_diff key
                        }
                    ],
                }
            ]
        )
    )
    assert '<del class="diff-tok-delete">viejo</del>' in html
    assert '<ins class="diff-tok-insert">nuevo</ins>' in html
