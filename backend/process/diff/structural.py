"""
Layer 1 of the hybrid bill-difference pipeline: structural parsing + alignment.

Parses a normalized bill text into a flat list of section nodes (TÍTULO,
CAPÍTULO, Artículo, etc.) and aligns the nodes of two versions so downstream
layers diff matched content, not unrelated sections.

Pure, side-effect-free, stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property

# ── Section patterns tuned for Peruvian legislative text ─────────────────────
#
# Anchors are matched at the start of a (stripped) line.  Ordering matters:
# more specific patterns must come before the generic article pattern so an
# "Artículo único" header is not swallowed as an article-by-number.

# v1 deliberately stops at article granularity.  Sub-article markers
# (``1.1``, ``a)``) stay inside their parent article's text and are handled
# by Layer 2's line diff — promoting them to top-level siblings would force
# document-order-dependent collision suffixes and let alignment cross
# article boundaries.  See the design doc for the tree-structured option.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "titulo",
        re.compile(r"^T[ÍI]TULO\s+([IVX]+|[ÚU]NICO|PRELIMINAR)\b", re.IGNORECASE),
    ),
    ("capitulo", re.compile(r"^CAP[ÍI]TULO\s+([IVX]+|[ÚU]NICO)\b", re.IGNORECASE)),
    (
        "disposiciones",
        re.compile(
            r"^DISPOSICIONES\s+(COMPLEMENTARIAS|TRANSITORIAS|FINALES|DEROGATORIAS|MODIFICATORIAS)",
            re.IGNORECASE,
        ),
    ),
    (
        "articulo",
        re.compile(r"^Art[íi]culo\s+([0-9]+|[ÚU]nico)[.\-º°]?", re.IGNORECASE),
    ),
]

# Compact regex used by ``_normalize_for_diff`` (in ``diff.py``) as a
# negative-lookahead: a single newline is preserved when the next line
# starts with any of these anchors, so OCR line-reflow doesn't merge an
# article-boundary newline into its neighbour.  Keep in sync with the
# patterns above.
HEADER_LOOKAHEAD_PATTERN = r"(?:Art[íi]culo|T[ÍI]TULO|CAP[ÍI]TULO|DISPOSICIONES)\s"

# Roman numerals → int, for stable sortable IDs.
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int:
    s = s.upper()
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = v
    return total


@dataclass
class StructuralNode:
    """One parsed section of a bill.

    `node_id` is a stable, content-independent identifier shared across
    versions when an article keeps its number (the primary alignment anchor).

    `body`, `fingerprint`, and `body_words` are cached: they are derived from
    `text` and computed lazily for the alignment passes. ``StructuralNode``
    is mutated during parsing (``text`` is filled in after construction), so
    do not access these properties before ``parse_structure`` finishes.
    """

    node_id: str
    kind: str
    label: str
    text: str

    @cached_property
    def body(self) -> str:
        """Text minus the header line, so a renumbered article fingerprints the same."""
        lines = self.text.splitlines()
        if lines and lines[0].strip() == self.label.strip():
            return "\n".join(lines[1:])
        return self.text

    @cached_property
    def fingerprint(self) -> str:
        """Stable short prefix of the whitespace-collapsed body, for bucket matching."""
        body = re.sub(r"\s+", " ", self.body).strip().lower()
        return body[:_FINGERPRINT_LEN]

    @cached_property
    def body_words(self) -> set[str]:
        """Lowercase word set of the body, used for Jaccard similarity."""
        return {w for w in re.findall(r"\w{3,}", self.body.lower())}


def _make_node_id(kind: str, raw: str) -> str:
    """Stable identifier for a section header.

    `Artículo 5` → `articulo_5`,  `TÍTULO III` → `titulo_3`,
    `Artículo único` → `articulo_unico`.
    """
    raw_u = raw.strip().upper()
    if raw_u in {"ÚNICO", "UNICO"}:
        return f"{kind}_unico"
    if raw_u == "PRELIMINAR":
        return f"{kind}_preliminar"
    if raw_u.isdigit():
        return f"{kind}_{int(raw_u)}"
    if all(ch in _ROMAN for ch in raw_u):
        return f"{kind}_{_roman_to_int(raw_u)}"
    # Fallback: a slug. Use Unicode-aware ``\w`` so accented letters survive
    # ("Constitución" → "constitución", not "constituci_n").
    slug = re.sub(r"[^\w]+", "_", raw.lower(), flags=re.UNICODE).strip("_")
    return f"{kind}_{slug or 'x'}"


def parse_structure(text: str) -> list[StructuralNode]:
    """Parse normalized text into a flat list of structural nodes.

    Returns at least one node: if no headers are found everything is wrapped
    in a single synthetic ``preamble`` node so downstream layers can still
    operate.
    """
    if not text:
        return []
    lines = text.splitlines()
    nodes: list[StructuralNode] = []
    seen_ids: set[str] = set()
    current: StructuralNode | None = None
    buffer: list[str] = []

    def _flush() -> None:
        if current is None:
            return
        current.text = "\n".join(buffer).strip("\n")

    for raw_line in lines:
        stripped = raw_line.strip()
        matched = False
        for kind, pattern in _PATTERNS:
            m = pattern.match(stripped)
            if not m:
                continue
            # Header found: close out the prior node, open a new one.
            _flush()
            label_token = m.group(1)
            node_id = _make_node_id(kind, label_token)
            # Disambiguate collisions (e.g. two unnumbered "Artículo único" in
            # an appendix) by appending a counter.
            base = node_id
            n = 1
            while node_id in seen_ids:
                n += 1
                node_id = f"{base}__{n}"
            seen_ids.add(node_id)
            current = StructuralNode(
                node_id=node_id,
                kind=kind,
                label=stripped,
                text="",
            )
            nodes.append(current)
            buffer = [stripped]
            matched = True
            break
        if not matched:
            if current is None:
                current = StructuralNode(
                    node_id="preamble",
                    kind="preamble",
                    label="(preamble)",
                    text="",
                )
                nodes.append(current)
                buffer = []
            buffer.append(raw_line)

    _flush()

    if not nodes:
        nodes.append(
            StructuralNode(
                node_id="root",
                kind="root",
                label="(root)",
                text=text,
            )
        )
    return nodes


# ── Alignment ───────────────────────────────────────────────────────────────


@dataclass
class Alignment:
    """One pairing produced by `align_nodes`.

    Exactly one of `a` / `b` may be ``None`` for deletions / insertions.
    `status` is the alignment strategy that produced the match — kept for
    observability so we can tune thresholds in production.
    """

    a: StructuralNode | None
    b: StructuralNode | None
    status: str


_JACCARD_THRESHOLD = 0.6
_FINGERPRINT_LEN = 60


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def align_nodes(
    a_nodes: list[StructuralNode],
    b_nodes: list[StructuralNode],
) -> list[Alignment]:
    """Match nodes from version A to version B.

    Strategy:
      1. ID match (cheap, correct most of the time).
      2. Content-fingerprint match for unmatched nodes (catches pure
         renumbering).
      3. Greedy Jaccard similarity for the residual (catches renumbered
         articles with light edits).
      4. Leftovers are emitted as pure deletions / insertions.
    """
    by_id_a = {n.node_id: n for n in a_nodes}
    by_id_b = {n.node_id: n for n in b_nodes}

    matched_a: set[str] = set()
    matched_b: set[str] = set()
    pairs: list[Alignment] = []

    # 1. ID match.
    for nid, a in by_id_a.items():
        if nid in by_id_b:
            pairs.append(Alignment(a=a, b=by_id_b[nid], status="id"))
            matched_a.add(nid)
            matched_b.add(nid)

    # 2. Fingerprint match.  Key by (kind, fingerprint) so two empty-bodied
    # nodes of different kinds (e.g. a standalone ``TÍTULO`` header with no
    # body vs an empty ``DISPOSICIONES`` line) don't share a bucket via the
    # empty string.  Without this guard, cross-kind matches surface as
    # garbage hunks once Layer 2 diffs an Artículo against a Título.
    fp_b: dict[tuple[str, str], list[StructuralNode]] = {}
    for n in b_nodes:
        if n.node_id in matched_b:
            continue
        fp_b.setdefault((n.kind, n.fingerprint), []).append(n)

    for a in a_nodes:
        if a.node_id in matched_a:
            continue
        bucket = fp_b.get((a.kind, a.fingerprint))
        if not bucket:
            continue
        b = bucket.pop(0)
        pairs.append(Alignment(a=a, b=b, status="fingerprint"))
        matched_a.add(a.node_id)
        matched_b.add(b.node_id)

    # 3. Greedy Jaccard.
    rem_a = [n for n in a_nodes if n.node_id not in matched_a]
    rem_b = [n for n in b_nodes if n.node_id not in matched_b]
    if rem_a and rem_b:
        scores: list[tuple[float, StructuralNode, StructuralNode]] = []
        for a in rem_a:
            for b in rem_b:
                if a.kind != b.kind and "preamble" not in (a.kind, b.kind):
                    # Don't match an article against a title.
                    continue
                s = _jaccard(a.body_words, b.body_words)
                if s >= _JACCARD_THRESHOLD:
                    scores.append((s, a, b))
        scores.sort(key=lambda t: -t[0])
        for s, a, b in scores:
            if a.node_id in matched_a or b.node_id in matched_b:
                continue
            pairs.append(Alignment(a=a, b=b, status="similarity"))
            matched_a.add(a.node_id)
            matched_b.add(b.node_id)

    # 4. Leftovers.
    for a in a_nodes:
        if a.node_id not in matched_a:
            pairs.append(Alignment(a=a, b=None, status="deleted"))
    for b in b_nodes:
        if b.node_id not in matched_b:
            pairs.append(Alignment(a=None, b=b, status="inserted"))

    # Stable order: by B position (new doc reading order), then A position.
    b_pos = {n.node_id: i for i, n in enumerate(b_nodes)}
    a_pos = {n.node_id: i for i, n in enumerate(a_nodes)}

    def _sort_key(p: Alignment) -> tuple[int, int]:
        return (
            b_pos.get(p.b.node_id, 10**9) if p.b else 10**9,
            a_pos.get(p.a.node_id, 10**9) if p.a else 10**9,
        )

    pairs.sort(key=_sort_key)
    return pairs
