# Progress

State of BEP Bench as of 26 September 2026. What exists, what was measured, what is
known to be missing. Next steps live in [06-roadmap.md](06-roadmap.md).

Repository: <https://github.com/mac999/bepbench>

---

## Status

| | |
| --- | --- |
| Commits | 5 (`88c2336` … `a81c7d5`) |
| Tests | **126**, all passing |
| Python | 8,183 lines (`bepkit/` + `tests/`) |
| Templates | 1,251 lines |
| CSS + JS | 2,530 lines (excluding vendored three.js) |
| Frameworks | 1,864 lines of YAML |
| Documentation | 956 lines |
| Deployed | No — Fly config present, never launched |

---

## What was built

### Research first

Read ISO 19650-1/-2/-5, NBIMS-US v4, the Penn State BIM PxP Guide v2.2, EN 17412-1 and
the BIMForum LOD Specification; surveyed Plannerly, ACC/Trimble/Dalux, Solibri/BIMQ, and
the two comparable open-source projects. Five gaps drove the design and are written up in
[01-research.md](01-research.md):

1. Nobody scores the plan document itself
2. Completeness gets confused with quality
3. The plan and the model are separate artefacts
4. Drafting is slow and produces generic text
5. Cloud-only tools are unusable for security-classified assets

### Scoring engine

Three separate numbers — coverage, required coverage, and a weighted depth score — because
they answer different questions and merging them lets box-ticking read as progress.

- Per-field depth expectations (`min_words`, `min_rows`, `min_items`); placeholder text
  ("TBD", "N/A", "???") scores 0.1 and raises an issue
- Cross-field consistency checks declared in the framework: `table_column_filled`,
  `min_rows`, `field_present`, `field_not_value`, `values_subset_of`, `values_cover`
- Blocking issues gate "ready to issue" independently of the score
- Recommendations ranked by the overall points each gap would recover

### Frameworks (YAML, not code)

| id | Source | Sections | Fields | Checks |
| --- | --- | ---: | ---: | ---: |
| `iso19650` | BS EN ISO 19650-2 | 16 | 68 | 13 |
| `nbims_us` | NBIMS-US v4 | 12 | 35 | 7 |
| `lite` | Condensed for small works | 6 | 17 | 3 |

Korean overlays translate display strings only — ids, option values and stored answers
stay canonical, so a plan means the same thing in both languages.

### Appointment stages

22 of the 68 ISO fields are marked delivery-only (TIDPs, mobilisation, confirmed CDE
rules, training). The same answers score **97.8** as a pre-appointment BEP and **66.6** as
a delivery BEP — the honest reading of both.

### buildingSMART IDS

The LOIN table exports as an XSD-valid IDS 1.0 document, and an attached model can be
validated against the plan's own requirements. Rows naming no IFC class are reported,
never guessed into a silent false positive.

```
bep ids export <plan> -o plan.ids
bep ids check  <plan> model.ifc --fail-on-error
```

### Version comparison

Field-level added / changed / removed between two snapshots or against the current state,
with each section's score movement beside it, so a score change has a cause.

### IFC viewer

ifcopenshell tessellates at upload into a binary buffer plus a JSON index; three.js
(vendored, no CDN) renders it beside the editor. Five render modes, section plane, object
tree grouped by storey or class, element property inspection. **The LOD written into the
plan filters what is drawn** — the connection that justifies putting the two side by side.

### AI assistance

Per-field draft / improve / expand / critique through a local Ollama model. The prompt
carries the framework clause, the depth the scorer will demand, and what the rest of the
plan already commits to. Nothing leaves the machine; nothing is saved without a click.

### Output

Word `.docx` with styled headings, native tables and a TOC field, plus Markdown, HTML and
JSON. Per the house rule on document metadata, the python-docx template's fingerprints are
scrubbed — `Application` emptied, stray thumbnail removed, 2013 template date replaced,
Company/Manager taken from the plan.

### Interface

Four-pane workspace (section navigator │ plan │ model │ properties) with draggable
splitters, menu bar, English/Korean, light/dark, and a no-JavaScript fallback. A full CLI
shares the service layer with the web app, so a plan can be started in the browser,
drafted in the terminal and gated in CI without the three disagreeing about what
"complete" means.

---

## Measured performance

Nothing is slow at the current scale:

| Operation | Cost |
| --- | --- |
| `score_project()` | 0.80 ms |
| `project.values()` | 0.12 ms |
| `PUT /api/…/values` (autosave round trip) | 20 ms median, 22 ms p90 |
| Editor page render | 6 ms |
| IFC inspect (Duplex, 295 products) | 0.33 s |
| IFC tessellate (236 renderable) | 0.84 s |

Every real limit is a scaling one — 6,556 B of geometry and one draw call per element.
The extrapolation table and what to do about it are in [06-roadmap.md](06-roadmap.md).

---

## Bugs found and fixed

Ten defects, each caught by testing against something real rather than by reading the code.

### Found by the test suite

| Bug | Cause |
| --- | --- |
| `url_for` crash on project creation | The editor route always needs a section id |
| Snapshot restore lost answers | Stale ORM collection after deleting rows |

### Found by using a real IFC model (Duplex_A)

| Bug | Cause |
| --- | --- |
| Openings and room volumes rendered as solids | `IfcOpeningElement` is a void, not an object — a third of the element count |
| Object tree grouped by room number, not storey | Furniture is contained by `IfcSpace`; needed the storey ancestor |
| Replaced model served stale geometry | Re-upload reuses the row id, and the payload had a 1-hour cache |

### Found by looking at the rendered screen

| Bug | Cause |
| --- | --- |
| **Editor blank at 1101–1500px** | `display:none` on a grid item shifts every later item one track left — the plan pane landed in the 0px navigator track. Covered 1280, 1366, 1440 |
| Panels scrolled as one document | The workspace was a document, not an app shell; sticky positioning gave up once content exceeded the viewport |
| Cards 100px too tall | The page container `.wrap` and the flex modifier `.row.wrap` shared a class name, so rows inherited 100px of page padding |
| Dashboard stat boxes misaligned | `.card + .card` stacking margin leaked into grid layouts, stretching the first card of each row |
| AI answered in the wrong language | The request used the cookie's language, not the page's |

Each fix carries a regression test. The pattern worth noting: **most were invisible in
code review and obvious the moment something real was rendered.**

---

## Known limits

Stated plainly so they are not rediscovered as surprises.

- **The score is our own rubric**, not an industry-recognised measure. It grades whether
  commitments are stated, specific and internally consistent — never whether a commitment
  is *right* for the project. See [03-scoring.md](03-scoring.md).
- **Element-to-requirement matching is string-based.** It reads well in a demo and is not
  an audit. IDS export is the path to real verification.
- **The viewer caps at 20,000 elements** and even that is impractical: 131 MB of payload
  and 20,000 draw calls. This is the top item on the roadmap.
- **SQLite assumes one writer.** Fine for a single information manager; multi-user
  authoring, permissions and approval do not exist.
- **No diff of attached models**, only of the plan text.
- **No pre/post-appointment split in NBIMS-US or Lite** — only the ISO framework is
  stage-aware.

---

## Environment

- Data directory: `~/.local/share/bep` (SQLite + uploaded models)
- Local server: gunicorn on `0.0.0.0:8080`, 1 worker / 8 threads
- AI: Ollama `qwen3:30b-instruct` on `localhost:11434`
- Demo plan: `riverside-interchange-phase-2`, ISO 19650-2, with `Duplex_A.ifc` attached

```bash
bep demo                          # worked example, ~87/100
bep ifc import <plan> docs/demo/Duplex_A.ifc
bep serve                         # http://127.0.0.1:8080
pytest -q                         # 126 tests
```

---

## Not done

- **Fly.io deployment** — config is written and never launched, by request
- **The roadmap's task 0** (performance regression tests) — prerequisite for the
  instancing and compression work that follows it
