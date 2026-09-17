# Configuration

Everything a team might reasonably want to change lives in JSON, not in Python.

## Where settings come from

Defaults ship in `bepkit/config_files/defaults.json`. Overrides are **deep-merged** over them
in this order, each winning over the last:

1. `$BEP_CONFIG` — a JSON file, or a directory of `*.json` files applied in name order
2. `./bep.config.json` in the working directory
3. `<data dir>/config.json` — the deployed instance's own settings

`bep config` prints what is in force and where it came from; `bep config --json` prints the
whole merged document. A malformed override is reported and skipped, never fatal.

A partial override is enough — only name the keys you want to change:

```json
{
  "ai": { "model": "qwen3:8b", "temperature": 0.2 },
  "scoring": { "ready_score": 75 },
  "viewer": { "lod": { "default": "350" } }
}
```

## `ai`

| Key | Meaning |
| --- | --- |
| `enabled` | Turns the assist panel and API off entirely |
| `provider` | `ollama` (default) or `openai_compatible` |
| `base_url` | `http://localhost:11434` for Ollama; the API root for the other |
| `model` | Preferred model, e.g. `qwen3:30b-instruct` |
| `fallback_models` | Tried in order when the preferred model is not installed |
| `temperature`, `top_p`, `num_ctx`, `num_predict` | Generation settings |
| `timeout_seconds` | Per request |
| `context_answers`, `context_chars_per_answer` | How much of the rest of the plan is put in the prompt |
| `strip_think_tags` | Removes `<think>…</think>` from reasoning models |
| `system_prompt` | The drafting persona and its prohibitions |
| `modes.draft / improve / expand / critique` | The instruction appended for each button |

The default provider is local on purpose: an ISO 19650-5 triage often classifies an asset as
sensitive, which rules out a hosted model.

## `viewer`

| Key | Meaning |
| --- | --- |
| `modes` | The render buttons: `id`, `label`, `opacity`, `wireframe`, `edges` |
| `default_mode` | Which one is active on load |
| `palette` | IFC class → colour, with a `default` |
| `max_elements` | Tessellation cap; beyond it the payload is truncated and flagged |
| `max_upload_mb` | Upload limit |
| `deflection_tolerance` | Mesh quality — lower is finer and heavier |
| `background_light` / `background_dark` | Canvas background per theme |
| `lod.default` | Level selected before the plan says otherwise |
| `lod.levels.<n>` | `label`, `note`, `geometry` (`mesh` or `bbox`), `include`, `exclude` |
| `lod.sections.<framework>` | Which field drives the LOD: `section`, `field`, optional `column` |

`include` accepts `"*"`; `exclude` then removes classes from it. `geometry: "bbox"` draws
elements as massing boxes, which is what LOD 100 is supposed to look like.

To make a framework of your own drive the viewer, add an entry to `lod.sections`:

```json
{ "viewer": { "lod": { "sections": {
  "my_framework": { "section": "deliverables", "field": "element_matrix", "column": "lod" }
} } } }
```

## `ui` and `scoring`

| Key | Meaning |
| --- | --- |
| `ui.split_ratio`, `ui.min_panel_px` | Default panel proportions |
| `ui.show_viewer_tab` | Hide the model pane for teams that do not use it |
| `scoring.ready_score` | Score needed to be "ready to issue" (default 65) |
| `scoring.ready_required_coverage` | Required-field coverage needed (default 90) |
| `scoring.presence_floor` | Credit for answering a field at all before depth (default 0.35) |

Raising `ready_score` makes the gate stricter for everyone; it is the single most useful knob
for an organisation that wants a house standard above the framework minimum.

## Adding a framework

Frameworks are YAML, not code. Drop a file into `bepkit/frameworks/`, or point
`BEP_FRAMEWORK_PATH` at your own directory (`:`-separated; later directories override
built-ins with the same id).

```yaml
id: house_standard
name: Acme House BEP
version: "1.0"
maturity_bands:
  - { min: 0,  label: "Draft" }
  - { min: 70, label: "Approved" }
sections:
  - id: basics
    title: Project Basics
    weight: 1.0
    intent: One line on why this section exists.
    fields:
      - id: project_name
        label: Project Name
        type: text
        required: true
      - id: uses
        label: BIM Uses
        type: table
        quality: { min_rows: 3 }
        columns:
          - { id: use,   label: Use,   type: text, required: true }
          - { id: owner, label: Owner, type: text, required: true }
checks:
  - id: uses_owned
    rule: table_column_filled
    section: basics
    field: uses
    column: owner
    severity: blocker
    message: "Every BIM use needs an owner."
```

**Field types**: `text`, `textarea`, `markdown`, `number`, `date`, `select`, `multiselect`,
`list`, `boolean`, `table`, `link`.
**Depth**: `quality.min_words`, `quality.min_rows`, `quality.min_items`.
**Check rules**: `table_column_filled`, `min_rows`, `field_present`, `field_not_value`,
`values_subset_of`, `values_cover`.

The framework is validated on load: duplicate ids, a `select` without options, a `table`
without columns or a check pointing at a missing field all raise immediately.

## Translating a framework

Add `bepkit/frameworks/locales/<framework_id>.<lang>.yaml`. Only display strings are
translated — ids, option values and stored answers stay canonical, so the same plan means the
same thing in both languages. Anything the overlay omits falls back to English, so a partial
translation is a valid translation.

```yaml
name: Acme 사내 BEP
sections:
  basics:
    title: 프로젝트 기본정보
    fields:
      project_name: { label: 프로젝트명 }
      uses:
        label: BIM 활용
        columns: { use: 활용, owner: 담당 }
```
