from backend.process.diff import PARSER_VERSION, compute_bill_difference
from backend.process.diff.pipeline import _normalize_for_diff
from backend.process.diff.line import line_diff
from backend.process.diff.structural import align_nodes, parse_structure
from backend.process.diff.word import word_diff


# ── compute_bill_difference type semantics ──────────────────────────────────


def test_both_none_returns_unavailable():
    result = compute_bill_difference(None, None)
    assert result["type"] == "unavailable"
    assert result["content"] is None


def test_old_none_returns_first_version():
    result = compute_bill_difference(None, "some text")
    assert result["type"] == "first_version"
    assert result["content"] is None


def test_equal_texts_returns_no_change():
    text = "line one\nline two\n"
    result = compute_bill_difference(text, text)
    assert result["type"] == "no_change"
    assert result["content"] is None


def test_different_texts_returns_modified_with_structured_payload():
    old = "Artículo 1.- Texto original del articulo uno.\n"
    new = "Artículo 1.- Texto modificado del articulo uno.\n"
    result = compute_bill_difference(old, new)
    assert result["type"] == "modified"
    payload = result["content"]
    assert payload["parser_version"] == PARSER_VERSION
    assert payload["summary"]["nodes_total"] >= 1
    # The single node should carry hunks with word-level diffs.
    changed = [n for n in payload["nodes"] if n["hunks"]]
    assert changed, "expected at least one node with hunks"
    hunk = changed[0]["hunks"][0]
    assert hunk["op"] in {"replace", "insert", "delete"}
    assert "word_diff" in hunk
    assert any(run["op"] != "equal" for run in hunk["word_diff"])


def test_new_none_is_unavailable():
    # Regression: missing new text (no BillText row for a later step) used
    # to render as "everything deleted". A later step with no extracted
    # text means we cannot diff — not that the body was removed.
    old = "Artículo 1.- Algo.\n"
    result = compute_bill_difference(old, None)
    assert result["type"] == "unavailable"
    assert result["content"] is None


# ── Size-ratio guard ────────────────────────────────────────────────────────


def test_large_size_ratio_returns_incomparable():
    old = "x " * 5000
    new = "y"
    result = compute_bill_difference(old, new)
    assert result["type"] == "incomparable"
    assert result["content"] is None


def test_ratio_just_under_threshold_is_modified_or_no_change():
    new = "word " * 10
    small_old = "word " * 99
    result = compute_bill_difference(small_old, new)
    assert result["type"] in ("modified", "no_change")


def test_empty_new_text_is_incomparable():
    # Regression: ``if new_text:`` treated the empty string as "skip the
    # size-ratio guard", which materialized an O(N) deletion payload when
    # OCR returned an empty body for the new version.
    old = "Artículo 1.- Algo." * 200  # ~5 KB
    result = compute_bill_difference(old, "")
    assert result["type"] == "incomparable"
    assert result["content"] is None


def test_empty_old_text_is_incomparable():
    # Symmetric: pre-creation / failed-extraction old side.
    new = "Artículo 1.- Algo." * 200
    result = compute_bill_difference("", new)
    assert result["type"] == "incomparable"
    assert result["content"] is None


# ── Normalization ───────────────────────────────────────────────────────────


def test_normalize_collapses_single_newlines():
    text = "first line\nsecond line\nthird line"
    norm = _normalize_for_diff(text)
    assert "\n" not in norm
    assert "first line" in norm
    assert "third line" in norm


def test_normalize_preserves_paragraph_breaks():
    text = "paragraph one\n\nparagraph two"
    norm = _normalize_for_diff(text)
    assert "\n\n" in norm or norm.count("\n") >= 1


def test_normalize_standardizes_quotes_and_dashes():
    text = "“hola” — mundo"
    norm = _normalize_for_diff(text)
    assert '"hola"' in norm
    assert "-" in norm
    assert "—" not in norm


def test_normalize_preserves_the_word_no():
    # Regression: an earlier version of this function NFKC-folded º → o and
    # then re-substituted "no\b" → "n°", silently corrupting every Spanish
    # "no" on both sides of the diff.
    text = "yo no sé y No se aplica"
    norm = _normalize_for_diff(text)
    assert " no " in norm
    assert "No " in norm
    assert "n°" not in norm


def test_normalize_preserves_ordinal_indicator():
    # º and ° must remain distinct from "o" after normalization.
    text = "nº 5 y n° 6"
    norm = _normalize_for_diff(text)
    assert "nº" in norm or "n°" in norm
    assert "no 5" not in norm
    assert "no 6" not in norm


def test_reflow_noise_produces_no_change():
    old = "Artículo 1. Se aprueba el presupuesto\npor el monto de S/ 1 000 000,00\npara el año fiscal 2023."
    new = "Artículo 1. Se aprueba el presupuesto por el monto de\nS/ 1 000 000,00 para el año fiscal 2023."
    result = compute_bill_difference(old, new)
    assert result["type"] == "no_change"


def test_real_change_still_detected_after_normalization():
    old = "Artículo 1. El monto es S/ 1 000 000,00\npara el año 2023."
    new = "Artículo 1. El monto es S/ 2 000 000,00\npara el año 2023."
    result = compute_bill_difference(old, new)
    assert result["type"] == "modified"
    # The change must surface in the word-level diff somewhere.
    payload = result["content"]
    all_tokens = []
    for node in payload["nodes"]:
        for hunk in node["hunks"]:
            for run in hunk["word_diff"]:
                if run["op"] == "delete" or run["op"] == "replace":
                    all_tokens.extend(run["a_tokens"])
                if run["op"] == "insert" or run["op"] == "replace":
                    all_tokens.extend(run["b_tokens"])
    assert "1" in all_tokens and "2" in all_tokens


# ── Layer 1: structural parsing ─────────────────────────────────────────────


def test_parse_structure_identifies_articles():
    text = "Artículo 1.- alpha\nbeta\nArtículo 2.- gamma\n"
    nodes = parse_structure(text)
    ids = [n.node_id for n in nodes]
    assert "articulo_1" in ids
    assert "articulo_2" in ids


def test_parse_structure_identifies_titulos_and_capitulos():
    text = "TÍTULO I\nCAPÍTULO II\nArtículo 1.- algo\n"
    nodes = parse_structure(text)
    kinds = [n.kind for n in nodes]
    assert "titulo" in kinds
    assert "capitulo" in kinds
    assert "articulo" in kinds


def test_parse_structure_handles_unstructured_text():
    nodes = parse_structure("just some prose without headers")
    assert len(nodes) == 1
    assert nodes[0].kind == "preamble"


def test_parse_structure_keeps_incisos_inside_parent_article():
    # v1 deliberately stops at article granularity so lettered subparagraphs
    # stay with their parent article (Layer 2 handles them).  A regression
    # here would mean we'd reintroduced the flat-sibling collision problem.
    text = (
        "Artículo 5.- Texto del articulo cinco.\n"
        "a) Primer inciso.\n"
        "b) Segundo inciso.\n"
        "Artículo 6.- Texto del articulo seis.\n"
        "a) Otro primer inciso.\n"
    )
    nodes = parse_structure(text)
    kinds = [n.kind for n in nodes]
    assert kinds.count("articulo") == 2
    assert "inciso" not in kinds
    # The incisos should live inside their article's text.
    art5 = next(n for n in nodes if n.node_id == "articulo_5")
    art6 = next(n for n in nodes if n.node_id == "articulo_6")
    assert "a) Primer inciso." in art5.text
    assert "b) Segundo inciso." in art5.text
    assert "a) Otro primer inciso." in art6.text


# ── Layer 1: alignment ──────────────────────────────────────────────────────


def test_align_nodes_matches_by_id():
    a = parse_structure("Artículo 1.- foo\nArtículo 2.- bar\n")
    b = parse_structure("Artículo 1.- foo edited\nArtículo 2.- bar\n")
    pairs = align_nodes(a, b)
    matched = {p.a.node_id: p.b.node_id for p in pairs if p.a and p.b}
    assert matched.get("articulo_1") == "articulo_1"
    assert matched.get("articulo_2") == "articulo_2"


def test_align_nodes_fingerprint_catches_renumbering():
    a = parse_structure("Artículo 5.- mismo texto exacto que sobrevive\n")
    b = parse_structure("Artículo 7.- mismo texto exacto que sobrevive\n")
    pairs = align_nodes(a, b)
    fp = [p for p in pairs if p.status == "fingerprint"]
    assert fp, "fingerprint alignment should match renumbered article"
    assert fp[0].a.node_id == "articulo_5"
    assert fp[0].b.node_id == "articulo_7"


def test_align_nodes_records_pure_insertion():
    a = parse_structure("Artículo 1.- algo\n")
    b = parse_structure("Artículo 1.- algo\nArtículo 2.- nuevo\n")
    pairs = align_nodes(a, b)
    inserted = [p for p in pairs if p.status == "inserted"]
    assert any(p.b and p.b.node_id == "articulo_2" for p in inserted)


def test_align_nodes_records_pure_deletion():
    a = parse_structure("Artículo 1.- algo\nArtículo 2.- viejo\n")
    b = parse_structure("Artículo 1.- algo\n")
    pairs = align_nodes(a, b)
    deleted = [p for p in pairs if p.status == "deleted"]
    assert any(p.a and p.a.node_id == "articulo_2" for p in deleted)


def test_fingerprint_does_not_pair_across_kinds():
    # Regression: when two nodes of different kinds have empty bodies they
    # both fingerprint to "" and previously got paired by step 2.  That
    # forwarded a cross-kind hunk (e.g. TÍTULO body vs DISPOSICIONES body)
    # to the line/word layers and produced garbage output.
    #
    # Construct A and B so that the only cross-version candidates with
    # matching fingerprints are of different kinds, then assert no
    # fingerprint match was produced.
    a = parse_structure("TÍTULO I\n\nArtículo 1.- algo\n")
    b = parse_structure("DISPOSICIONES COMPLEMENTARIAS\n\nArtículo 1.- algo\n")
    pairs = align_nodes(a, b)
    fp = [p for p in pairs if p.status == "fingerprint"]
    assert fp == [], (
        "fingerprint step should not have paired the empty-bodied "
        f"TÍTULO with the empty-bodied DISPOSICIONES; got {fp!r}"
    )
    # The unmatched headers should surface as a pure deletion + insertion.
    statuses = {(p.status, (p.a or p.b).kind) for p in pairs}
    assert ("deleted", "titulo") in statuses
    assert ("inserted", "disposiciones") in statuses


# ── Layer 2: line diff ──────────────────────────────────────────────────────


def test_line_diff_basic_replace():
    hunks = line_diff("alpha\nbeta\ngamma\n", "alpha\nBETA\ngamma\n")
    assert len(hunks) == 1
    assert hunks[0]["op"] == "replace"
    assert "beta" in hunks[0]["a_text"]
    assert "BETA" in hunks[0]["b_text"]


def test_line_diff_omits_equal_runs():
    hunks = line_diff("same\nsame\n", "same\nsame\n")
    assert hunks == []


def test_line_diff_pure_insertion():
    hunks = line_diff("alpha\n", "alpha\nbeta\n")
    assert len(hunks) == 1
    assert hunks[0]["op"] == "insert"
    assert hunks[0]["b_text"] == "beta"


# ── Layer 3: word diff ──────────────────────────────────────────────────────


def test_word_diff_inline_change():
    runs = word_diff("monto es 1000", "monto es 2000")
    non_equal = [r for r in runs if r["op"] != "equal"]
    assert non_equal
    # Confirm we kept the equal runs around the changed token.
    assert any(r["op"] == "equal" and "monto" in r["a_tokens"] for r in runs)


def test_word_diff_punctuation_is_its_own_token():
    runs = word_diff("hola, mundo", "hola; mundo")
    diffs = [r for r in runs if r["op"] != "equal"]
    assert diffs
    # The change should be a single-token replacement of comma → semicolon.
    flat_a = [t for r in diffs for t in r["a_tokens"]]
    flat_b = [t for r in diffs for t in r["b_tokens"]]
    assert "," in flat_a
    assert ";" in flat_b


# ── End-to-end JSON shape ───────────────────────────────────────────────────


def test_payload_is_json_serializable():
    import json

    old = "Artículo 1.- alpha\nArtículo 2.- beta\n"
    new = "Artículo 1.- alpha\nArtículo 2.- beta editado\n"
    result = compute_bill_difference(old, new)
    assert result["type"] == "modified"
    serialized = json.dumps(result["content"])
    roundtrip = json.loads(serialized)
    assert (
        roundtrip["summary"]["nodes_total"]
        == result["content"]["summary"]["nodes_total"]
    )


def test_compute_bill_difference_finds_multiple_articles_end_to_end():
    # Regression: the line-reflow step in ``_normalize_for_diff`` used to
    # collapse every single newline to a space, so by the time the
    # structural parser ran the whole body was one line and only the first
    # article header was ever matched.  Layer 1 was silently a no-op on
    # real bills.  The fix preserves newlines that precede a known header
    # anchor.
    old = (
        "Artículo 1.- Objeto de la Ley\n"
        "La presente ley regula el procedimiento.\n"
        "Artículo 2.- Ámbito de aplicación\n"
        "Se aplica a todas las organizaciones civiles.\n"
    )
    new = (
        "Artículo 1.- Objeto de la Ley\n"
        "La presente ley regula el procedimiento.\n"
        "Artículo 2.- Ámbito de aplicación\n"
        "Se aplica a todas las personas naturales y juridicas.\n"
    )
    result = compute_bill_difference(old, new)
    assert result["type"] == "modified"
    payload = result["content"]
    assert payload["summary"]["nodes_total"] >= 2, (
        "structural parser should see both Artículo 1 and Artículo 2 "
        "as distinct nodes — see backend/process/diff.py _normalize_for_diff"
    )
    node_ids = [n["node_id"] for n in payload["nodes"]]
    assert "articulo_2" in node_ids
    # And the change should land inside articulo_2 specifically.
    art2 = next(n for n in payload["nodes"] if n["node_id"] == "articulo_2")
    assert art2["hunks"], "articulo_2 should carry the edit"


def test_ocr_broken_header_still_normalizes_to_one_line():
    # The other side of the fix: when OCR splits a header across a line
    # break (``Artículo\n1.-``), reflow SHOULD still join — the next line
    # doesn't *start* with the anchor word, it's a continuation of one.
    old = "Artículo\n1.- alpha"
    norm = _normalize_for_diff(old)
    assert "Artículo 1.- alpha" in norm


def test_indented_header_survives_reflow():
    # Regression: an earlier fix used a header negative-lookahead anchored
    # immediately after ``\n``.  Real OCR commonly indents section anchors;
    # the lookahead missed those and the article got swallowed back into
    # the preamble.  Confirm an indented header (any amount of leading
    # whitespace) is now preserved as its own line.
    from backend.process.diff.structural import parse_structure

    norm = _normalize_for_diff("preamble text\n   Artículo 5.- contenido")
    node_ids = [n.node_id for n in parse_structure(norm)]
    assert "articulo_5" in node_ids, f"got {node_ids!r}"


def test_indented_titulo_also_survives():
    from backend.process.diff.structural import parse_structure

    norm = _normalize_for_diff("body\n\t\tTÍTULO II\nsiguiente")
    node_ids = [n.node_id for n in parse_structure(norm)]
    assert "titulo_2" in node_ids, f"got {node_ids!r}"
