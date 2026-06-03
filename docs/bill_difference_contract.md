# Bill Difference Frontend Contract

The bill-difference page shows the textual differences between two consecutive
versions of a bill. This document is the contract between the renderer
(server-side, in `app/`) and the frontend code (Jinja templates, CSS, JS, or a
separate SPA) that consumes it.

If you are restyling the page, localizing it, adding interactivity, or
building a separate client, start here.

---

## 1. URL

| Property | Value |
|---|---|
| URL | `/bills/<bill_id>/difference/<int:step_id>` |
| Method | `GET` |
| Parameters | `bill_id` (string, e.g. `2021_6127`), `step_id` (int) |
| Returns | HTML page (200), or `304 Not Modified` |
| Auth | none |

`step_id` identifies the *new* version. The previous version (if any) is
looked up from the bill's step ordering.

---

## 2. Response states

The template branches on `difference_type`. Five cases:

| `difference_type` | When | What the template emits |
|---|---|---|
| `modified` | Texts differ after normalization | The rendered diff (see §3), or `<p class="diff-status diff-status-warning">No difference data available.</p>` if the payload fails to parse or render |
| `no_change` | Texts equal after normalization | `<p class="diff-status diff-status-equal">` |
| `first_version` | No prior version exists | `<p class="diff-status diff-status-info">` |
| `incomparable` | Size ratio > 10× — probably mismatched documents | `<p class="diff-status diff-status-warning">` |
| `unavailable` | Diff row missing, or the new step has no extracted text yet | `<p class="diff-status diff-status-warning">` |

If `difference_content` is present but the route fails to JSON-decode it,
or the renderer raises, the route logs the exception and the template
takes the same "No difference data available" fallback. The page still
returns `200`.

---

## 3. HTML structure of a `modified` diff

The diff fragment is wrapped in a single root element:

```html
<div class="diff-rendered" data-renderer-version="1">
  …
</div>
```

`data-renderer-version` is the stability signal — see §5.

### Inside that root

```
.diff-rendered
├── .diff-summary
│     └── .diff-summary-pill                (one per non-zero stat)
│         .diff-summary-changed             (always present)
│         .diff-summary-inserted            (only if N > 0)
│         .diff-summary-deleted             (only if N > 0)
│         .diff-summary-renamed             (only if N > 0)
│
└── .diff-node.diff-node-{status}           (one per section that changed)
    │   status ∈ { matched, inserted, deleted }
    │
    ├── .diff-node-header
    │     ├── .diff-node-badge.diff-node-badge-{status}
    │     ├── .diff-node-id           (the canonical id, e.g. "articulo_5")
    │     ├── .diff-node-label        (human label, e.g. "Artículo 5.-")
    │     └── .diff-node-strategy     (only when match_strategy ≠ id/inserted/deleted)
    │
    └── .diff-hunk.diff-hunk-{op}            (one or more per node)
          │   op ∈ { insert, delete, replace }
          │
          ├── .diff-hunk-header
          │     ├── .diff-hunk-op           (literal op name)
          │     └── .diff-hunk-range        ("lines a[X–Y] → b[X–Y]")
          │
          └── .diff-hunk-body                 (the inline word diff)
                ├── <span class="diff-tok-equal">unchanged words</span>
                ├── <ins class="diff-tok-insert">added words</ins>
                └── <del class="diff-tok-delete">removed words</del>
                (interleaved in document order)
```

### Notes on element choice

* Inserted / deleted tokens use real `<ins>` / `<del>` elements, not
  `<span>`s. Screen readers announce these correctly without ARIA work.
* Equal tokens use `<span>` because there is no semantic element for
  "unchanged in a diff."
* Token text is always HTML-escaped before insertion. Nothing in the
  document body is `safe`-marked.

---

## 4. CSS classes — what each one means

You can restyle any of these. The renderer guarantees the names; the
*visual treatment* is yours.

### Status pills (top of diff)

| Class | When emitted |
|---|---|
| `.diff-status` | Wrapper for any "no diff to show" status message |
| `.diff-status-equal` | "No changes between versions." |
| `.diff-status-info` | "First version" / "Legacy format" |
| `.diff-status-warning` | "Incomparable" / "Unavailable" |

### Summary pills

| Class | Content |
|---|---|
| `.diff-summary` | Flex row of pills |
| `.diff-summary-pill` | One pill, always at least one (the total) |
| `.diff-summary-changed` | Number of sections that changed (always emitted) |
| `.diff-summary-inserted` | Sections added in v2 (only if > 0) |
| `.diff-summary-deleted` | Sections removed in v2 (only if > 0) |
| `.diff-summary-renamed` | Sections matched by content despite renumbering (only if > 0) |

### Node sections

| Class | Meaning |
|---|---|
| `.diff-node` | One bill section (typically one article) |
| `.diff-node-matched` | Section present in both versions, with changes |
| `.diff-node-inserted` | Section added in v2 |
| `.diff-node-deleted` | Section removed from v1 |
| `.diff-node-badge-{status}` | Small label in the node header |
| `.diff-node-id` | The canonical id (stable across versions when possible) |
| `.diff-node-label` | The human-readable header line from the bill |
| `.diff-node-strategy` | Hint about how alignment was found (`fingerprint`, `similarity`) |

### Hunks (changes inside a section)

| Class | Meaning |
|---|---|
| `.diff-hunk` | One contiguous change within a node |
| `.diff-hunk-insert` | Lines added |
| `.diff-hunk-delete` | Lines removed |
| `.diff-hunk-replace` | Lines changed |
| `.diff-hunk-header` | Op + line range |
| `.diff-hunk-body` | The inline word-level diff (renders as a single paragraph) |

### Inline tokens

| Class | Element | Meaning |
|---|---|---|
| `.diff-tok-equal` | `<span>` | Unchanged text |
| `.diff-tok-insert` | `<ins>` | Added text (highlight green) |
| `.diff-tok-delete` | `<del>` | Removed text (highlight red, strikethrough) |

---

## 5. Versioning and stability

The renderer is versioned via the `RENDERER_VERSION` constant in
`app/diff_render.py`. Every rendered fragment carries it as
`data-renderer-version` on the root.

**Stability promise within a major version:**

* Class names listed in §4 will not be removed or renamed.
* The nesting documented in §3 will not be reshaped.
* New classes may be *added* (e.g. to mark new metadata). Frontend code
  should ignore unknown classes gracefully.

**When `RENDERER_VERSION` is bumped:**

* The contract may have changed in a backwards-incompatible way.
* Stored ETags become invalid; clients automatically refetch.
* A migration note should appear in this document explaining the change.

Frontend code that wants to fail fast on unknown versions can check
`document.querySelector('.diff-rendered').dataset.rendererVersion`.

---

## 6. Caching

The route sets these headers on every `200` response:

```
ETag: "bd-<bill_id>-<step_id>-<difference_type>-<content_hash>-r<RENDERER_VERSION>"
Cache-Control: public, max-age=300, stale-while-revalidate=86400
```

Implications for the frontend:

* Repeat visits within the cache window return `304 Not Modified` from
  the server with no body. The browser uses the previously cached HTML.
  No frontend work required — `fetch` and `XMLHttpRequest` both honor this.
* If you build a SPA that bypasses the browser cache (e.g. setting
  `cache: 'no-store'`), you re-render-cost on every navigation. Don't do
  that.
* If you proxy through a CDN, the response is `public` and safe to share
  across users.
* `stale-while-revalidate` means after 5 min, the CDN/browser serves the
  stale response immediately and refreshes in the background. Tune via the
  `Cache-Control` header in `app/routes/bills.py` if needed.

---

## 7. Code locations

| What | Where |
|---|---|
| Route | `app/routes/bills.py` (`bill_difference`) |
| Renderer | `app/diff_render.py` (`render_payload_html`) |
| Renderer tests | `tests/app/test_diff_render.py` |
| Template | `app/templates/bills/difference.html` |
| CSS | `app/static/css/layout.css` (search for "Hybrid diff renderer") |
| Structured payload schema | `backend/process/diff/pipeline.py` (`_build_payload` docstring) |

---

## 8. Reference sample

Five real diffs rendered end-to-end with the live renderer + CSS, suitable
for visual review:

```
data/processed/sample_bill_differences.html       (open in any browser)
data/processed/sample_bill_differences.json       (the underlying rows)
```

Use these as fixtures when designing new visual treatments. They cover the
common cases:

* Bill `2021_6127` — single-token accent fix (`INTERES` → `INTERÉS`)
* Bill `2021_11511` — single-token accent fix (`TRAVÉS` → `TRAVES`)
* Bill `2021_10413` — multi-word insertion
* Bill `2021_530` — OCR garbage replaced by real preamble text
* Bill `2021_2788` — full-text replacement (small → large)

---

## 9. Building a separate client (SPA)

If you want to render diffs in React / Vue / Svelte instead of consuming
the server-rendered HTML, none of the above is what you want — you want
the structured payload directly.

This requires backend work that isn't done yet:

1. **A JSON endpoint** alongside the existing HTML route, e.g.
   `GET /api/bills/<bill_id>/difference/<step_id>` returning the
   `difference_content` object from the DB. Roughly 15 lines in
   `app/routes/bills.py`.
2. **CORS** if the SPA is on a different origin.
3. **A JS port of the renderer.** The Python in `app/diff_render.py` is
   ~150 lines; a JS twin will need the same token-joining rules around
   punctuation and Spanish-specific opening marks (`¿`, `¡`).

The structured payload schema is documented in
`backend/process/diff/pipeline.py` (`_build_payload` docstring). It looks like:

```json
{
  "parser_version": 1,
  "summary": {
    "nodes_total": 3,
    "nodes_changed": 2,
    "nodes_inserted": 1,
    "nodes_deleted": 0,
    "nodes_renamed": 0
  },
  "nodes": [
    {
      "node_id": "articulo_5",
      "kind": "articulo",
      "status": "matched",
      "match_strategy": "id",
      "a_label": "Artículo 5.-",
      "b_label": "Artículo 5.-",
      "hunks": [
        {
          "op": "replace",
          "a_start": 2, "a_end": 3,
          "b_start": 2, "b_end": 3,
          "a_text": "monto es S/ 1 000",
          "b_text": "monto es S/ 2 000",
          "word_diff": [
            {"op": "equal",   "a_tokens": ["monto","es","S","/"], "b_tokens": ["monto","es","S","/"]},
            {"op": "replace", "a_tokens": ["1"],                   "b_tokens": ["2"]},
            {"op": "equal",   "a_tokens": ["000"],                 "b_tokens": ["000"]}
          ]
        }
      ]
    }
  ]
}
```

Ask backend before going down this path — keeping two renderers in sync
is real ongoing cost.

---

## 10. Known gaps (areas worth improving)

These are not blockers; the page works. They're flagged so future PRs
don't relitigate them.

* **Hunk-header copy is English.** "changed", "renumbered", "lines a[…]",
  "via similarity". When localizing to Spanish, edit `app/diff_render.py`
  — the strings are inline, no gettext yet.
* **No expand/collapse.** Real bills can have 50+ nodes. JS to toggle
  `.diff-node` visibility (and a "show all" / "hide unchanged" toggle in
  the summary row) would help. The DOM is already structured for it.
* **Raw `<pre>` blocks at the top of the page** dump both full bill
  bodies. Consider hiding behind a "Show source" disclosure.
* **Mobile media query** only handles `.diff-versions`. Node cards and
  hunk bodies need attention on phones.
* **Color-only state indicators.** Inserted/deleted are distinguished by
  color. Pair with icons or different border treatments for color-blind
  users.
* **Long equal-text runs inside one hunk** render as a single wrapped
  paragraph. If a hunk has thousands of unchanged words around a small
  change, the page gets a wall of text. Splitting on `\n` in the equal
  runs is a small renderer change if it becomes a problem.
