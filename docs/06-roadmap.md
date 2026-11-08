# Roadmap

Priorities by value for effort, differentiation and measured performance, as of
November 2026. Every number below was measured on this machine against the bundled
Duplex model, not estimated from intuition.

## Where the project actually stands

**Nothing is slow at the current scale.** Measured on the demo plan:

| Operation | Cost |
| --- | --- |
| `score_project()` | 0.80 ms |
| `project.values()` | 0.12 ms |
| `PUT /api/…/values` (autosave round trip) | 20 ms median, 22 ms p90 |
| Editor page render | 6 ms |
| IFC inspect (Duplex, 295 products) | 0.33 s |
| IFC tessellate (236 renderable) | 0.84 s |

The problems are all **scaling limits**, not present-day latency. Optimising the scoring
engine would be wasted work.

---

## The scaling wall

Extrapolated from the Duplex payload: 6,556 B of geometry and 238 B of index per element,
one draw call per element, 3.6 ms to tessellate each.

| Model size | Binary buffer | `index.json` | Tessellation | Draw calls |
| --- | ---: | ---: | ---: | ---: |
| 236 (bundled demo) | 1.5 MB | 0.06 MB | 0.8 s | 236 |
| 20,000 (current cap) | **131 MB** | 4.8 MB | 1.2 min | 20,000 |
| 150,000 (mid infrastructure) | **983 MB** | 36 MB | 9 min | 150,000 |
| 500,000 (large infrastructure) | **3.3 GB** | 119 MB | 30 min | 500,000 |

Even the configured 20,000-element cap is unusable: it means a 131 MB download and 20,000
draw calls. The tool talks about interchange projects and opens a house.

---

## Priorities

### 1. Geometry instancing — best value for effort

**Measured basis.** In the Duplex, 236 elements resolve to **47 distinct types**: 95% of
elements share a type with at least one other, a **5× ceiling** on unique geometry. Real
buildings repeat doors, windows and furniture far more, so 10–20× is realistic.

Tessellate once per `IfcTypeObject`, store only the transform per occurrence, and render
with `THREE.InstancedMesh`. This cuts upload time, payload size and draw calls **at the
same time** — the only change that hits all three bottlenecks at once.

- Effort: **medium** (`ifcio/loader.py` payload format + `viewer.js` render path)
- Risk: **low** — the payload format extends; keep the per-element path as a fallback
- Gate: needs task 6 first, to prove the gain rather than assert it

### 2. Mesh compression (meshopt / Draco)

Compress the unique geometry that survives instancing, and quantise vertex positions from
float32. Worth a further **3–4×**, multiplying with task 1 for a combined 20–80×. This is
settled industry practice rather than a bet — mesh compression is standard in every
browser CAD pipeline.

- Effort: **small–medium** (a decoder in the viewer, an encoder at upload)
- Risk: **low**

### 3. Binary index and per-storey streaming

At 238 B per element, a 500,000-element index is 119 MB of JSON parsed on the main thread.
Replace it with a fixed-width binary index and load geometry in storey or zone chunks, so
the first paint does not wait for the whole model. Research on spatial-semantic partitioning
supports chunking on the spatial structure that IFC already carries.

- Effort: **medium**
- Risk: **medium** — touches the viewer's selection and filter paths

---

### 4. Put IDS at the front — differentiation, no performance work

Research finding: **IDS adoption is still early**. Most authoring software does not support
it yet; BIMcollab is among the few to have taken it through a whole product line. Meanwhile
public procurement and regulatory compliance are pushing towards auditable, machine-checkable
information requirements.

**A tool that generates IDS from the execution plan is close to unique.** BEP Bench already
does it, and the README lists it fifth. Repositioning from "another BEP authoring tool" to
"the BEP → IDS pipeline" costs no code and is the cheapest differentiation available.

Worth building on top:

- **bSDD integration** — done in 0.7.0: the classification system resolves to its dictionary URI
- **IDS → BCF reports** — done in 0.6.0: the failures land in the tools people already review issues in
- **Better IFC class resolution** — the current keyword inference is honest about being a
  guess, but the fewer guesses the better

- Effort: **small–medium**
- Risk: **low**

---

### 5. Multi-user — the largest structural gap, but not yet

A real BEP is written by the appointing party and several appointed parties together.
Authoring, permissions, comments and approval are the core of the commercial tools and are
absent here.

**Not now, on value for effort.** It means authentication, authorisation, concurrent editing
and conflict resolution, and it breaks the single-writer SQLite assumption. Building it
before there are real users spends the largest budget on the least evidence.

Cheap substitute that captures most of the value: **a read-only share link plus comments**.

- Effort: full feature **large**; share link **small**

---

### 6. Performance regression tests — prerequisite for 1–3

Done in 0.9.0 at the first size: `tests/test_perf.py` generates a 1,000-wall model
(`bepkit/ifcio/synthetic.py`), times tessellation and measures payload per element, and
fails when the `perf.*` budget is crossed. CI runs it on every push. The 10k and 50k sizes
and the draw-call count wait for task 1, which is what they measure.

- Effort: **small**
- Risk: none; it is the safety net for everything else

---

## Suggested order

Revised October 2026, after practitioner feedback on the first public release: the value of
a BEP tool lies in the open standards it supports, not in its model viewer. That moves IDS
to the front and puts the viewer's scaling work on hold.

```
4 (IDS)  ·  then, only when a user brings a model past the cap:  6 → 1 → 2 → 3
```

**Task 4 comes first.** Its first part is done: one IDS per milestone, every attached model
checked in its own schema, classes checked against the target schema, subtypes covered, and
real property sets, and a class pick list in the LOIN table (0.5.0). See
[07-standards.md](07-standards.md); the check's failures leave as BCF issues (0.6.0) and
the classification facet points at bSDD (0.7.0). What follows is the read-only share link
from task 5, then 6 → 1 → 2 → 3 when a model hits the cap.

**Tasks 6 → 1 → 2 → 3 wait for evidence.** They remain the right order if the
20,000-element cap starts to bite, and the measurements above still hold. Spending the
largest budget before anyone hits the limit is the mistake task 5 already avoids.

Task 5 still waits for real users.

---

## Known limits carried forward

Stated plainly so they are not rediscovered as surprises:

- **The score is our own rubric**, not an industry-recognised measure. It grades whether
  commitments are stated, specific and internally consistent — never whether a commitment
  is *right* for the project. See [03-scoring.md](03-scoring.md).
- **Classes are inferred from element names** when a LOIN row does not name one. The
  inference is reported, but a wrong guess checks the wrong elements; a class picker in
  the table (task 4) removes the guess.
- **SQLite assumes one writer.** Fine for a single information manager; see task 5.
- **No version diff of attached models**, only of the plan text.

---

## Sources

- [ThatOpen Fragments — IFC importer and streaming](https://docs.thatopen.com/Tutorials/Fragments/Fragments/IfcImporter/)
- [ThatOpen engine_fragment — stream parser discussion](https://github.com/ThatOpen/engine_fragment/issues/310)
- [Browser-based CAD review: WebGPU, glTF, compression](https://novedge.com/blogs/design-news/design-software-history-enabling-immersive-browser-based-cad-review-webxr-gltf-usd-webassembly-and-webgpu)
- [Dynamically loading IFC models by spatial semantic partitioning](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7099568/)
- [buildingSMART — Information Delivery Specification](https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/)
- [What is the buildingSMART IDS standard (adoption status)](https://www.nordicbim.com/en/insights/what-is-the-buildingsmart-ids-standard)
- [BIMcollab introduces the IDS standard](https://www.bimcollab.com/en/resources/news/ids-release/)
- [IDS and bSDD for automating information exchange and verification](https://www.mdpi.com/2075-5309/15/3/378)
