# Research: how BIM Execution Plans are written today

Notes gathered before designing this tool, with what each finding implied for the build.

## The standards that define the content

| Source | What it fixes | Used here |
| --- | --- | --- |
| **BS EN ISO 19650-2:2018** | The delivery-phase information management process: EIR → BEP → MIDP/TIDP, the CDE states, and the pre/post-appointment split. | The `iso19650` framework: 16 sections, 68 fields, mapped clause by clause. |
| **UK BIM Framework guidance (Part 2)** and the CDBB *Pre-appointment and Delivery Team's BEP Guidance* | What an appointing party actually expects to read, and the container naming convention. | Section intents, the naming-convention field, and the status/revision code table. |
| **NBIMS-US v4 Project BIM Execution Planning Standard** | A twelve-clause US structure: metadata, project reference, contacts, roles, BIM uses, process maps, information exchanges, collaboration, quality, technology, model federation and standards, risk register. | The `nbims_us` framework. |
| **Penn State BIM Project Execution Planning Guide v2.2** | The four-step procedure: identify high-value BIM uses, map the process, define information exchanges, then build the supporting infrastructure. | The ordering and weighting of the NBIMS framework; the "value vs capability vs proceed" columns on the BIM use table. |
| **EN 17412-1** | Level of Information Need — geometrical detail, alphanumeric information, documentation. | The LOIN table in the ISO framework, which is also what drives the model viewer's LOD filter. |
| **BIMForum LOD Specification** | LOD 100–500 as discrete, checkable levels. | The LOD matrix in the NBIMS framework and the viewer's LOD rules. |
| **ISO 19650-5** | Security-minded approach: triage, classification, handling. | The security section, and a check that refuses to let a plan claim readiness while triage is outstanding. |

## What existing tools do

**Plannerly** is the closest product: templates aligned to ISO 19650 / PAS 1192 / AIA / BIMForum, browser editing with live collaboration, embedded rich content (draw.io process maps, Matterport, BIM 360 models), one-click branded document output, and a BIM-requirements-to-deliverable validation loop.

**Autodesk Construction Cloud, Trimble Connect, Dalux, BIMcollab** own the CDE and the issue workflow. The BEP tends to live in them as an uploaded PDF — a document *about* the process, stored next to but disconnected from the process.

**Solibri, BIMQ, Cobuilder** work the requirements side: model checking and data-requirement definition. They validate the model against a rule set, but the rule set is authored separately from the BEP that promised it.

**The default in practice remains a Word template.** Most BEPs are a 40-page document derived from a house template, reviewed by eye.

### What that leaves open

1. **No score.** Reviewers judge a BEP by reading it. Two reviewers disagree, and a delivery team cannot self-assess before submitting. Research on BIM maturity (the BIM Maturity Index, ARUP's BIM Maturity Measure, the Penn State/NBIMS planning guides) grades *organisations and projects* — not the plan document itself.
2. **Completeness is confused with quality.** A template filled with "TBD" is 100% complete and worth nothing.
3. **The plan and the model are separate artefacts.** The BEP states a level of information need; nothing checks that the model delivered matches it, and the author cannot see the model while writing the requirement.
4. **Drafting is slow and generic.** Teams copy last project's text. It is consistent, and often wrong.
5. **Cloud-only tools are a problem for sensitive assets.** ISO 19650-5 triage frequently classifies transport, utility and defence assets as sensitive, which rules out pasting the plan into a hosted LLM.

## What this tool does about it

| Gap | Response |
| --- | --- |
| No score | A weighted scoring engine with depth expectations per field, placeholder detection, cross-field consistency checks, and a blocking-issue gate. See `docs/03-scoring.md`. |
| Completeness ≠ quality | Coverage and score are reported as separate numbers, and placeholder text scores near zero. |
| Plan vs model | The IFC viewer sits beside the editor, filtered by the LOD the plan itself declares; selecting an element shows what the plan demands of that element. |
| Slow drafting | Per-field AI assistance whose prompt carries the framework clause, the depth expected, and what the rest of the plan already commits to. |
| Sensitive assets | The default provider is a local Ollama model. Nothing leaves the machine. |

### Sources

- [ISO 19650-2 Guidance Part 2 — UK BIM Framework](https://ukbimframework.org/wp-content/uploads/2020/05/ISO19650-2Edition4.pdf)
- [Pre-appointment and Delivery Team's BEP Guidance — CDBB](https://www.cdbb.cam.ac.uk/files/bep_guidance.pdf)
- [NBIMS-US v4 Project BIM Execution Planning Standard](https://nibs.org/nbims/v4/bep/)
- [BIM Project Execution Planning Guide v2.2 — Penn State](https://psu.pb.unizin.org/bimprojectexecutionplanningv2x2/front-matter/executive_summary/)
- [BIM Project Execution Planning Guide v2.1 (PDF) — NIBS](https://nibs.org/wp-content/uploads/2025/04/NBIMS-US_V3_5.3_BIM_PxP_Guide.pdf)
- [Plannerly — BEP software](https://plannerly.com/plan/) and their [16-point BEP checklist](https://plannerly.com/bep-bim-execution-plan-guide/)
- [BIM Maturity Matrix — BIM Excellence](https://bimexcellence.org/files/301in-BIM-Maturity-Matrix.pdf)
- [How BIM is Assessed Using ARUP's BIM Maturity Measure](https://www.arcom.ac.uk/-docs/proceedings/c4544915428d4c013c8156dad3cb923a.pdf)
