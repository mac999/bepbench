# Revision history

Versions follow semantic versioning: a minor number for new features, a patch number for
fixes and documentation. Each version is tagged in git (`v0.4.0`).

## 0.7.3 — 2026-11-08 — Confirm before removing a model

- *Remove model* asks for confirmation and names the file before deleting it.
- New test renders every section of every framework in both languages, scores it and
  exports it in all four formats.

## 0.7.2 — 2026-11-08 — Remove model from the viewer toolbar

- *Remove model* sits next to *Upload IFC* in the viewer toolbar and acts on the shown
  model, instead of a × on each row of the model list.

## 0.7.1 — 2026-11-04 — Property data types from the Pset template

- A property facet requires the data type its standard property set template defines, so
  `Pset_WallCommon.IsExternal` asks for an `IfcBoolean` instead of failing every wall for
  not being an `IfcLabel`. A property no template defines is left open to any type.
  `ids.data_type` set to a value forces that type on every property as before;
  `ids.data_types` names one per property.

## 0.7.0 — 2026-11-04 — bSDD dictionary URIs

- The classification facet carries the bSDD URI of the system the plan names, resolved from
  `ids.bsdd_dictionaries` (Uniclass 2015, CCI, NL-SfB, ETIM, IFC out of the box) or, with
  `ids.bsdd_lookup`, from the bSDD API. The *Requirements* tab and `bep ids export` say
  which dictionary was matched; `bep ids bsdd <name>` resolves a name on its own.
- The *Classification System* field offers the configured names; a framework field may
  name a pick list with `suggest:`, as a table column can since 0.5.0.

## 0.6.0 — 2026-11-04 — BCF issues from a check

- A model's failures against the plan's requirements download as a BCF 2.1 file, one
  issue per failed specification with every failing element in its viewpoint
  (`ids.bcf_topic_per = element` for one issue each). The *Requirements* tab offers it
  per model, `GET /api/projects/<slug>/models/<id>/bcf` serves it, and `bep ids check
  --bcf DIR` writes one per failing model. Needs `bcf-client`, now part of the `ids` extra.

## 0.5.0 — 2026-11-04 — IFC class pick list

- The *IFC Class* cell of the LOIN table offers every instantiable class the target schemas
  define (`ids.class_root`, `ids.class_schemas`) and marks a typed name none of them
  defines. Typing stays allowed. `GET /api/ifc/classes` and `bep ids classes` give the same
  list with the schemas defining each class.
- A framework column may name a pick list with `suggest:`; the editor renders it as a
  datalist, so a house framework can offer its own lists.

## 0.4.3 — 2026-10-30 — Viewer spinner fix

- The loading spinner over the 3D view clears once the model is shown. The overlay's own
  `display` overrode the `hidden` attribute; a global `[hidden]` rule now wins.

## 0.4.2 — 2026-10-29 — Fixes from an end-to-end pass

- A requirement on a class also covers its instantiable subtypes, so `IfcWall` now
  matches the `IfcWallStandardCase` elements an IFC2X3 export is made of
  (`ids.include_subtypes`). On the Duplex model it now covers 57 walls instead of 1.
- Plural element names infer their class: *Windows* → `IfcWindow`.
- The viewer reloads a script dropped while the server wakes, and says so when it
  cannot; an upload that succeeded is no longer reported as failed.
- A rejected upload leaves no broken model in the list.
- Malformed API input returns 400 with a message instead of 500: a JSON body that is
  not an object, `null` text fields, a malformed import, a non-numeric model id.
- A batch of values with one bad value applies none of them.
- Settings refuse a blank name or an unknown stage instead of crashing.
- The JSON export API returns Word documents as base64.
- New end-to-end test of a plan built from scratch.

## 0.4.1 — 2026-10-27 — Demo app on Fly.io

- The README links a public demo app at https://bepbench.fly.dev/, with the sample plan and
  model loaded; AI drafting is off there, as the server runs no language model.

## 0.4.0 — 2026-10-26 — Requirements tab

- New *Requirements* tab in the editor: pick a milestone, download its IDS, see what was
  skipped or inferred, and check every attached model, each with its own result.
- *Model → Check* opens the tab; the model list shows each model's last result.
- A specification with nothing to apply to is reported as N/A, not as passed.
- One segmented-control style across the viewer, object tree, AI panel and the new tab.
- Fly.io deployment moves to Tokyo (`nrt`); ifcopenshell and ifctester are pinned below 0.10.

## 0.3.0 — 2026-10-25 — IDS by milestone, every model checked

- IDS export cuts by milestone (`--milestone`) or writes one file per milestone (`--split`);
  the web Model menu lists each milestone.
- `bep ids check` and the web check cover every attached model, each in its own IFC schema.
- A class the target schema lacks is reported instead of silently passing.
- `Pset_DoorCommon.FireRating` in the LOIN table is required in that property set.
- Every IDS value is a setting; `bep --set key=value` overrides any setting for one run.
- New *Structured Data Responsibility Matrix* in the ISO framework (69 fields).
- New [docs/07-standards.md](docs/07-standards.md); roadmap puts IDS ahead of viewer scaling.

## 0.2.1 — 2026-10-22 — Acknowledgement

- Credit for the Duplex Apartment model in the README.

## 0.2.0 — 2026-10-14 — RunPod deployment and live demo

- `deploy/runpod.sh` with data on the persistent volume and basic authentication.
- Port conflicts reported clearly; installs into a virtualenv; service restarts with the pod.
- Optional unauthenticated serving; live demo linked from the README.

## 0.1.1 — 2026-09-26 — Layout fixes, roadmap and progress record

- Editor no longer blanks at 1101–1500px; card margins no longer leak into grids.
- Roadmap with measured scaling limits, and a progress record.

## 0.1.0 — 2026-09-18 — Initial release

- BEP authoring and scoring for ISO 19650-2, NBIMS-US v4 and a Lite template.
- buildingSMART IDS export, IFC viewer, local AI drafting, Word export, CLI, English and Korean.
