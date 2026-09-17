# Feature and UX structure

## Information architecture

```
Dashboard  ── portfolio score, blocking issues, plans as cards
  │
  ├─ New plan ── pick a framework (ISO 19650-2 / NBIMS-US v4 / Lite)
  ├─ Import ──── a .json export
  │
  └─ Plan workspace
       ├─ Section editor      one framework section at a time  ← the default screen
       │    ├─ left    section navigator with per-section completion
       │    ├─ centre  the fields of this section (+ per-field AI assist)
       │    ├─ centre  IFC model canvas, filtered by the plan's LOD
       │    └─ right   properties of the selected element / live assessment
       ├─ Score              full report: sections, issues, recommendations, snapshots
       ├─ Document           printable preview and export (.md / .html / .json)
       └─ Settings           metadata, duplicate as a house template, delete

Frameworks ── browse the templates: sections, fields, depth expectations, checks
```

## The workspace

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ BEP  File  Plan  Model  View  Help   / Riverside Interchange   ☰   EN KO  ◐   │  menu bar
├──────────┬─────────────────────┬──╥────────────────────────┬──╥──────────────┤
│ sections │ BEP input           │  ║  BIM model canvas      │  ║ object tree  │
│          │                     │  ║                        │  ║  ▾ Ground Fl.│
│ 01 ●  100│ Level of Information│  ║   [Solid|Transparent|  │  ║    ▸ Wall  3 │
│ 02 ●   79│ Need          *req  │  ║    X-ray|Wireframe]    │  ║    ▸ Slab  1◉│
│ 03 ◐   61│ ┌─────────────────┐ │  ║                        │  ║  ▾ First Fl. │
│ 04 ◐   44│ │ Element │ LOD   │ │  ║      ▄▟██████▙▄        │  ╟──────────────┤
│ …        │ │ Deck    │ [400] │ │  ║    ▟██████████▙       │  ║ IfcSlab      │
│          │ └─────────────────┘ │  ║                        │  ║ First floor  │
│          │        ✦ AI draft   │  ║  LOD 400 · 15/15 shown │  ║ BEP asks:    │
│          │                     │  ║                        │  ║ LOD 400      │
└──────────┴─────────────────────┴──╨────────────────────────┴──╨──────────────┘
                                  splitter                 splitter
```

Four panes on one screen: the section navigator, the plan, the model, and the object
tree with the selected element's properties beneath it. Both splitters drag, respond to
arrow keys when focused, and remember their position per browser. `☰` collapses the
navigator; **View → Reset the panel layout** restores the defaults. Below 1100px the
panes stack vertically.

## Menu bar

| Menu | Contents |
| --- | --- |
| **File** | New plan · All plans · Import · **Save as Word (.docx)** · Export ▸ Markdown / HTML / JSON · Print / Save as PDF · Duplicate · Project settings |
| **Plan** | Go to section ▸ (every section) · **Completeness assessment** · Take a snapshot · Snapshot history · Framework reference |
| **Model** | Attach an IFC model · Render mode ▸ · Level of development ▸ (and *Follow the plan*) · Fit in view · Section plane · Remove model |
| **View** | Section navigator · Theme ▸ light / dark / system · Language ▸ EN / 한국어 · Reset the panel layout |
| **Help** | Keyboard shortcuts · About |

The menu is the discoverable route to everything the panels also expose inline. Word export
and the completeness assessment sit at the top level of their menus because they are the two
things a BIM manager does at the end of a drafting session.

## Object tree

Built from the uploaded model's payload, grouped **by storey** (Site → Storey → IFC class →
element) or **by class**, with a filter box for large models.

- Click an element → it is selected in the canvas and its properties appear below.
- Click an element in the canvas → the tree scrolls to it and highlights it.
- The ◉ column hides a whole branch; the canvas element count updates as it goes.
- Counts per branch make a missing discipline obvious at a glance.

## Principles behind the layout

**One section at a time.** A 68-field form in one scroll is how Word templates get filled
with "TBD". Each screen is one framework clause with its intent, its guidance and its own
score, and the navigator shows where you are in the whole.

**The score is always visible, never modal.** Every keystroke autosaves and returns a fresh
score; the ring, the section bar, the per-field state badges and the "highest-value gaps"
list repaint from the same response. The author sees the cost of vagueness immediately.

**Say what is missing, not just how much.** Each field shows why it is not complete —
"31 words, expected around 60", "3 of 5 rows", "required cells left blank" — and the
recommendation list is ordered by how many points completing it recovers, so a team with
an hour to spend knows where to spend it.

**The model belongs next to the plan.** The LOD written into the LOIN table drives what the
viewer draws. Set LOD 100 and the model collapses to massing boxes; set 400 and every
fixing appears. Clicking an element shows its IFC properties and, beside them, the
requirement this plan places on it — or a warning that no requirement matches it.

**AI drafts, the author commits.** Suggestions are never written automatically. The panel
offers Draft / Improve / Expand / Critique, shows the model and the time taken, and leaves
insertion to a deliberate click.

## Primary flows

### Author a plan
`Dashboard → New plan → framework → Section 01` → fill, autosave, `⌘S` to flush, `Next section →`
→ `Score` → fix blocking issues → `Snapshot` → `Document → Download`.

### Assess a plan you received
`Import` a JSON export, or author it → `Score`. Blocking issues first, then major, each
linking straight to the field that caused them.

### Check a model against the plan
`Section editor → Model tab → Upload IFC` → the viewer filters to the plan's LOD → click an
element → the right pane shows its properties and the plan's requirement for it.

### Gate a submission in CI
`bep score <plan> --require-ready --fail-under 70` exits non-zero until the plan passes.

## Screen inventory

| Screen | Purpose | Key interactions |
| --- | --- | --- |
| Dashboard | Portfolio view | Score rings, blocking-issue count, new plan, import |
| Section editor | Authoring | Autosave, table editor (Tab adds a row), AI assist, LOD sync |
| Model canvas | Coordination | Render modes, LOD strip, class chips, section plane, picking |
| Object tree | Navigation | Storey/class grouping, filter, branch visibility, two-way selection |
| Properties | Inspection | IFC attributes and psets, plus the BEP requirement for the element |
| Assessment rail | Feedback | Live score, section issues, highest-value gaps |
| Score | Review | Section table, full issue list, recommendations, snapshots |
| Document | Output | Printable preview and Word / Markdown / HTML / JSON export |
| Settings | Admin | Metadata, duplicate as template, delete with typed confirmation |
| Frameworks | Transparency | Every section, field, weight and check the score is based on |

## Interface details that carry weight

- **Two numbers, not one.** Coverage answers "how much is filled in"; the score answers
  "is it usable". Showing both stops box-ticking from reading as progress.
- **Issue severity is a gate, not a colour.** A blocking issue prevents "ready to issue"
  regardless of score.
- **Language and theme are per reader.** EN/KO switch in the top bar, dark and light follow
  the system unless overridden. Framework content is translated by overlay files; ids,
  option values and stored answers never change.
- **Keyboard.** `⌘/Ctrl+S` flushes pending saves, `⌘/Ctrl+Enter` moves to the next section,
  `Tab` from the last table cell adds a row, arrow keys resize a focused splitter.
- **No-JavaScript fallback.** Each section is a real form that posts and saves.
