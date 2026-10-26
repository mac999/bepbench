# Standards and how they relate

What each standard is, how much it is used in practice, which document contains which,
and where BEP Bench draws its lines. Checked October 2026.

## How much each one is used

| Standard | What it is | In practice |
| --- | --- | --- |
| **BEP** (ISO 19650-2) | The delivery team's plan in answer to the appointing party's requirements | Core contract document wherever ISO 19650 is adopted |
| **IFC** (ISO 16739-1:2024, IFC4.3 ADD2) | The open BIM data schema | Widely required for delivery; quality of exports varies |
| **LOIN** (ISO 7817-1:2024, formerly EN 17412-1) | How to state the level of information need | Concept standardised in 2024; many teams still write "LOD" |
| **IDS** 1.0 (buildingSMART, June 2024) | Machine-checkable form of information requirements | Early but rising; tool support is self-reported |
| **COBie** | Facility handover data exchange | Strong in the UK and US federal work, uneven elsewhere |
| **MVD** | A subset of IFC that software implements | Chosen daily as an export option (Coordination View 2.0, Reference View); authoring mvdXML is being phased out by buildingSMART |
| **IDM** (ISO 29481) | Method for defining processes and exchanges | Used by standards developers, rarely seen on a project |

## Which document contains which

```
OIR  organisational information requirements
├─ AIR  asset information requirements
└─ PIR  project information requirements
    └─ EIR  exchange information requirements ........ one per appointment
        ├─ LOIN  level of information need
        │   └─ IDS ............................... one per milestone, n specifications
        │       └─ bSDD  dictionary URIs it may reference
        └─ BEP  the delivery team's response ........ one per appointment, pre and post
            ├─ MIDP
            │   └─ TIDP .......................... one per task team
            ├─ exchange formats: IFC schema and MVD
            └─ structured data responsibilities (COBie or the operator's schema)

IFC schema
└─ MVD  subset a tool implements (CV2.0, Reference View, COBie)
    └─ IFC files ............................... n per delivery, by discipline and container
        └─ checked against the IDS for their milestone

IDM: the process definition behind both an MVD and an IDS
```

## Where BEP Bench draws its lines

**One plan is one appointment's BEP.** A project with several appointments has several
plans. Holding many appointments in one plan would change the data model for little gain.

**One plan produces one IDS per milestone.** The LOIN table names a milestone on every row,
and a Stage 3 model must not be checked against Stage 4 requirements. `bep ids export
--milestone 3` cuts one; `--split` writes one file per milestone. In the web app the
*Requirements* tab picks the milestone once, and both the download and the model check use
it. The default, with no milestone, is every row in one document.

**One plan is checked against every model attached to it.** A plan has a model per
discipline. `bep ids check` runs against each, in each model's own schema, and reports them
separately; `--model-id` narrows it. A specification that applies to nothing in a model is
reported as not applicable rather than passed.

**A class the target schema lacks is reported, never exported.** `IfcCourse` exists only in
IFC4X3. Aimed at an IFC4 model, a specification for it would match nothing and pass. The
row is listed as skipped instead, or the specification is narrowed to the schemas that
define the class.

**Requirements name real property sets.** `Pset_DoorCommon.FireRating` in the table is
required in `Pset_DoorCommon`, which is where authoring tools write it. A property written
without a set goes into `ids.default_pset`, and the export says how many did.

**IDS, not MVD.** BEP Bench states project requirements, which is the job IDS was made for.
It does not author MVDs. An MVD defines what software must implement, buildingSMART is
retiring mvdXML as an authoring format, and no official MVD exists for many IFC4.3 domains,
roads among them. A tool that waited for one could not write a road BEP.

**NBIMS-US follows the planning clauses only.** The `nbims_us` framework mirrors the v4
execution-planning clause structure and the Penn State procedure. It makes no claim about
COBie V3 conformance or about whether a model satisfies NBIMS.

**Structured data is a matrix, whatever the standard.** The ISO framework's *Structured Data
Responsibility Matrix* has one row per data group: standard and version, producing task
team, due date, validation. COBie 2.4, COBie 3, HVACie or an operator's own schema are all
values in the same column, so supporting another standard needs no new feature.

## Sources

- [IDS v1.0 approved as a final standard — buildingSMART](https://www.buildingsmart.org/information-delivery-specification-ids-v1-0-is-approved-as-a-final-standard/)
- [IDS software implementations — buildingSMART Technical](https://technical.buildingsmart.org/ids-software-implementations/)
- [mvdXML — buildingSMART Technical](https://technical.buildingsmart.org/standards/ifc/mvd/mvdxml/)
- [ISO 16739-1:2024](https://www.iso.org/standard/84123.html)
- [New level of information need standard published — BIM Plus](https://bimplus.co.uk/new-level-of-information-need-standard-published)
- [ISO 19650 Guidance Part 2 — UK BIM Framework](https://www.ukbimframework.org/wp-content/uploads/2021/02/Guidance-Part-2_Parties-teams-and-processes-for-the-delivery-phase-of-assets_Edition-6.pdf)
- [COBie V3 — NIBS](https://nibs.org/nbims/v3/cobie/)
