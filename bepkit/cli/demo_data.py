"""A worked example plan.

Deliberately not perfect: a few sections are left thin so the score, the issues
and the "highest-value gaps" list all have something real to show.
"""

DEMO_VALUES: dict[str, object] = {
    "project_information.project_name": "Riverside Interchange — Phase 2",
    "project_information.project_number": "RIV-2026-002",
    "project_information.appointing_party": "City Transport Authority",
    "project_information.lead_appointed_party": "Harbour & Slate Engineering",
    "project_information.project_stage": "3 Spatial Coordination",
    "project_information.bep_status": "Post-appointment (delivery)",
    "project_information.project_description": (
        "Phase 2 replaces the eastbound viaduct deck and rebuilds the interchange concourse, "
        "including a new 4,200 m2 passenger building, two lift cores and the relocation of the "
        "primary electrical intake. The appointment covers detailed design through to handover "
        "of the asset information model, under an NEC4 Option C target cost contract. Phase 1 "
        "earthworks are complete and their as-built survey is reference information for this "
        "appointment. Rail possessions constrain construction to eight weekend windows, which "
        "drives the coordination programme far harder than the design programme does."
    ),
    "project_information.revision_history": [
        {"revision": "P01", "date": "2026-02-10", "author": "J. Salim",
         "summary": "Pre-appointment BEP issued with tender", "approved_by": "R. Okafor"},
        {"revision": "P02", "date": "2026-04-02", "author": "J. Salim",
         "summary": "Post-appointment update: task teams and CDE confirmed", "approved_by": "R. Okafor"},
        {"revision": "C01", "date": "2026-05-18", "author": "M. Tanaka",
         "summary": "LOIN table expanded for Stage 4; clash matrix agreed", "approved_by": "R. Okafor"},
    ],

    "objectives_uses.bim_goals": (
        "The appointing party's overriding information goal is to take possession risk out of the "
        "weekend closures. Every information decision is judged against whether it lets a works "
        "package be assembled, checked and rehearsed before the possession starts. Second, the "
        "operator wants an asset information model that can be loaded into their existing CAFM "
        "without manual re-keying, which sets the structured data requirements in section 13. "
        "Third, the design team must be able to demonstrate spatial coordination of the concourse "
        "services zone at each gateway, because the ceiling void is the tightest constraint on the "
        "project and has already absorbed one design change."
    ),
    "objectives_uses.bim_uses": [
        {"use": "Design authoring", "priority": "Core", "owner": "Architecture task team",
         "stage": "3-4", "output": "Federated discipline models at each gateway"},
        {"use": "3D coordination", "priority": "Core", "owner": "BIM coordination team",
         "stage": "3-5", "output": "Weekly clash report and BCF issue register"},
        {"use": "4D construction sequencing", "priority": "Core", "owner": "Construction planning",
         "stage": "4-5", "output": "Possession-by-possession sequence animation and review sign-off"},
        {"use": "Quantity take-off", "priority": "Secondary", "owner": "Commercial team",
         "stage": "4", "output": "Model-derived quantities reconciled to the cost plan"},
        {"use": "Asset information handover", "priority": "Core", "owner": "Information management",
         "stage": "5-6", "output": "Validated asset data drop against the AIR"},
        {"use": "Existing conditions modelling", "priority": "Secondary", "owner": "Survey team",
         "stage": "3", "output": "Registered point cloud and derived reference model"},
    ],
    "objectives_uses.success_measures": [
        {"measure": "Unresolved critical clashes at gateway", "target": "Zero",
         "method": "Navisworks clash report against the agreed matrix", "frequency": "Per gateway"},
        {"measure": "Information containers delivered on the MIDP date", "target": "≥ 95%",
         "method": "CDE delivery log audit", "frequency": "Monthly"},
        {"measure": "Asset data fields populated at handover", "target": "100% of AIR-mandated fields",
         "method": "Automated schema validation", "frequency": "Per data drop"},
        {"measure": "Rework instructions traced to coordination failure", "target": "Fewer than 5 per possession",
         "method": "Site instruction review", "frequency": "Per possession"},
    ],

    "team_roles.org_structure": (
        "Harbour & Slate Engineering is the lead appointed party and holds the information "
        "management function. Four task teams sit beneath it: architecture, structures, building "
        "services and civils/permanent way. The specialist facade contractor is appointed directly "
        "by the appointing party and joins the delivery team as a fifth task team by agreement, "
        "with the same CDE obligations but a separate appointment."
    ),
    "team_roles.key_roles": [
        {"function": "Information management (lead appointed party)", "organisation": "Harbour & Slate",
         "name": "J. Salim", "contact": "j.salim@example.com", "deputy": "M. Tanaka"},
        {"function": "Project information manager (appointing party)", "organisation": "City Transport Authority",
         "name": "R. Okafor", "contact": "r.okafor@example.gov", "deputy": "P. Lindqvist"},
        {"function": "BIM coordination", "organisation": "Harbour & Slate",
         "name": "M. Tanaka", "contact": "m.tanaka@example.com", "deputy": "A. Byrne"},
        {"function": "CDE administration", "organisation": "Harbour & Slate",
         "name": "A. Byrne", "contact": "a.byrne@example.com", "deputy": "J. Salim"},
        {"function": "Asset information (operator)", "organisation": "City Transport Authority",
         "name": "P. Lindqvist", "contact": "p.lindqvist@example.gov", "deputy": ""},
    ],
    "team_roles.task_teams": [
        {"team": "Architecture task team", "discipline": "Architecture",
         "scope": "Concourse building, finishes, wayfinding", "lead": "S. Mbeki"},
        {"team": "Structures task team", "discipline": "Structural engineering",
         "scope": "Deck replacement, lift cores, foundations", "lead": "D. Ferreira"},
        {"team": "Building services task team", "discipline": "MEP",
         "scope": "Concourse services, electrical intake, drainage", "lead": "H. Novak"},
        {"team": "Civils task team", "discipline": "Civils and permanent way",
         "scope": "Highway realignment, track interface, drainage outfall", "lead": "K. Adeyemi"},
        {"team": "BIM coordination team", "discipline": "Coordination",
         "scope": "Federation, clash, issue management", "lead": "M. Tanaka"},
    ],
    "team_roles.raci": [
        {"activity": "Federate discipline models", "responsible": "BIM coordination team",
         "accountable": "J. Salim", "consulted": "Task team managers", "informed": "R. Okafor"},
        {"activity": "Authorise container transition to Shared", "responsible": "Task team manager",
         "accountable": "J. Salim", "consulted": "BIM coordination team", "informed": "Task teams"},
        {"activity": "Accept information at a milestone", "responsible": "R. Okafor",
         "accountable": "R. Okafor", "consulted": "P. Lindqvist", "informed": "Delivery team"},
        {"activity": "Maintain the MIDP", "responsible": "J. Salim", "accountable": "J. Salim",
         "consulted": "Task team managers", "informed": "R. Okafor"},
        {"activity": "Run and report clash detection", "responsible": "M. Tanaka",
         "accountable": "J. Salim", "consulted": "Task team managers", "informed": "R. Okafor"},
    ],
    "team_roles.capability_summary": (
        "All five task teams were assessed against the appointing party's capability questionnaire "
        "at tender. The civils task team scored below threshold on IFC export competence; that gap "
        "is carried as risk R-04 and is closed by the training plan in section 15 before the Stage 4 "
        "data drop."
    ),

    "information_requirements.reference_documents": [
        {"document": "Exchange Information Requirements", "reference": "CTA-EIR-004 Rev C",
         "issued_by": "City Transport Authority", "date": "2026-01-15"},
        {"document": "Asset Information Requirements", "reference": "CTA-AIR-002 Rev B",
         "issued_by": "CTA Asset Management", "date": "2025-11-30"},
        {"document": "CTA Information Protocol", "reference": "CTA-IP-2024",
         "issued_by": "City Transport Authority", "date": "2024-06-01"},
    ],
    "information_requirements.eir_response": [
        {"clause": "3.1", "requirement": "Federated model at each gateway",
         "response": "Complied", "how": "Federation produced weekly; gateway issue is the Friday federation of that week"},
        {"clause": "3.4", "requirement": "IFC 4 export of all discipline models",
         "response": "Partially complied",
         "how": "Civils models export via IFC 2x3 until the authoring tool upgrade in July; deviation logged as D-01"},
        {"clause": "4.2", "requirement": "Asset data delivered per AIR schema",
         "response": "Complied", "how": "Automated validation against CTA-AIR-002 before each drop"},
        {"clause": "5.1", "requirement": "Security-minded approach per ISO 19650-5",
         "response": "Complied", "how": "Triage completed; sensitive asset controls applied — see section 12"},
        {"clause": "6.3", "requirement": "Weekly clash reporting",
         "response": "Complied", "how": "Reported every Thursday with BCF issues raised in the CDE"},
        {"clause": "7.1", "requirement": "Point cloud survey of existing viaduct",
         "response": "Deviation proposed",
         "how": "Possession access prevents full underside capture; photogrammetry proposed for soffit — awaiting decision"},
    ],
    "information_requirements.information_purposes": (
        "Information is produced to support four decisions: gateway design acceptance at Stage 3 and "
        "Stage 4, possession readiness sign-off before each weekend window, contractor procurement of "
        "the facade and lift packages, and the operator's acceptance of the asset information model at "
        "handover. Anything not serving one of those decisions is not modelled to a higher level of "
        "information need than the framework requires."
    ),
    "information_requirements.loin": [
        {"element": "Viaduct deck structure", "lod": "400", "stage": "4", "geometry": "Fabrication-ready profile, connections modelled",
         "alphanumeric": "Grade, mass, fabrication reference, install sequence ID",
         "documentation": "Fabrication drawings, mill certificates", "owner": "Structures task team"},
        {"element": "Concourse services zone", "lod": "300", "stage": "3", "geometry": "Coordinated routes with maintenance envelopes",
         "alphanumeric": "System reference, duty, flow rate", "documentation": "Schematic set", "owner": "Building services task team"},
        {"element": "Lift cores", "lod": "350", "stage": "4", "geometry": "Shaft, guide rails, pit and overrun",
         "alphanumeric": "Capacity, speed, supplier reference", "documentation": "Supplier submittal", "owner": "Architecture task team"},
        {"element": "Electrical intake", "lod": "350", "stage": "4", "geometry": "Switchroom layout with clearance zones",
         "alphanumeric": "Rating, protection settings, asset tag", "documentation": "Single line diagram", "owner": "Building services task team"},
        {"element": "Highway realignment", "lod": "300", "stage": "3", "geometry": "Corridor surface and kerb lines",
         "alphanumeric": "Chainage, surfacing spec", "documentation": "Setting-out data", "owner": "Civils task team"},
    ],

    "delivery_strategy.milestones": [
        {"milestone": "Stage 3 spatial coordination gateway", "stage": "3", "date": "2026-06-26",
         "purpose": "Design acceptance and release of the facade package",
         "acceptance": "Zero critical clashes, LOIN met for all Stage 3 elements, issue register clear"},
        {"milestone": "Stage 4 technical design data drop", "stage": "4", "date": "2026-10-09",
         "purpose": "Construction release and possession planning",
         "acceptance": "IFC export validated, 4D sequence approved, asset data schema check passed"},
        {"milestone": "Possession 1 readiness", "stage": "5", "date": "2027-01-15",
         "purpose": "Possession go / no-go decision",
         "acceptance": "Sequence rehearsed in 4D, temporary works models federated and clash free"},
        {"milestone": "Asset information handover", "stage": "6", "date": "2027-09-30",
         "purpose": "Operator acceptance of the asset information model",
         "acceptance": "100% of AIR-mandated fields populated and validated"},
    ],
    "delivery_strategy.tidp_summary": [
        {"team": "Architecture task team", "container": "RIV-HSE-ZZ-XX-M3-A-0001", "format": "RVT + IFC4",
         "milestone": "Stage 3 gateway", "author": "S. Mbeki", "reviewer": "M. Tanaka"},
        {"team": "Structures task team", "container": "RIV-HSE-ZZ-XX-M3-S-0001", "format": "RVT + IFC4",
         "milestone": "Stage 3 gateway", "author": "D. Ferreira", "reviewer": "M. Tanaka"},
        {"team": "Building services task team", "container": "RIV-HSE-ZZ-XX-M3-M-0001", "format": "RVT + IFC4",
         "milestone": "Stage 3 gateway", "author": "H. Novak", "reviewer": "M. Tanaka"},
        {"team": "Civils task team", "container": "RIV-HSE-ZZ-XX-M3-C-0001", "format": "DGN + IFC2x3",
         "milestone": "Stage 4 data drop", "author": "K. Adeyemi", "reviewer": "M. Tanaka"},
        {"team": "BIM coordination team", "container": "RIV-HSE-ZZ-XX-M3-Z-0001", "format": "NWD",
         "milestone": "Weekly", "author": "M. Tanaka", "reviewer": "J. Salim"},
    ],
    "delivery_strategy.midp_approach": (
        "Each task team maintains its TIDP in the shared planning workbook on the CDE. The information "
        "manager aggregates them into the MIDP every second Friday and baselines it at each gateway. "
        "When the construction programme moves, the MIDP is re-issued within five working days and any "
        "container whose date moved by more than ten days is escalated at the delivery team meeting."
    ),
    "delivery_strategy.mobilisation": (
        "Mobilisation ran over three weeks in March: CDE folder structure and permissions tested with a "
        "dummy container through all four states, template files issued and validated by each task team, "
        "and a federation dry run proving that IFC exports from all five authoring tools land on the "
        "shared origin without manual repositioning."
    ),

    "cde_workflow.cde_platform": "Autodesk Construction Cloud — administered by Harbour & Slate, licensed by the appointing party",
    "cde_workflow.cde_states": [
        {"state": "Work in Progress", "purpose": "Task team's own development",
         "entry": "Created by the task team; not visible outside it", "approver": "Task team manager"},
        {"state": "Shared", "purpose": "Coordination between task teams",
         "entry": "Passes the three pre-share checks and carries status S1-S4", "approver": "Task team manager"},
        {"state": "Published", "purpose": "Authorised information for the appointing party",
         "entry": "Reviewed by the information manager and accepted by the appointing party", "approver": "R. Okafor"},
        {"state": "Archive", "purpose": "Audit trail of superseded containers",
         "entry": "Automatic on supersede; retained for the contractual period", "approver": "CDE administrator"},
    ],
    "cde_workflow.naming_convention": (
        "Containers follow the UK National Annex convention: Project-Originator-Volume-Level-Type-Role-Number, "
        "for example RIV-HSE-EB-02-M3-S-0001. Volume codes EB (eastbound viaduct), CN (concourse) and ZZ "
        "(project-wide) are fixed at mobilisation and may not be extended without the information manager's "
        "agreement, because the CDE permission rules key off the volume segment."
    ),
    "cde_workflow.status_codes": [
        {"code": "S0", "meaning": "Work in progress", "suitability": "Task team internal use only"},
        {"code": "S2", "meaning": "Shared for information", "suitability": "Coordination and reference"},
        {"code": "S4", "meaning": "Shared for construction approval", "suitability": "Approval by the appointing party"},
        {"code": "A1", "meaning": "Authorised and accepted", "suitability": "Construction"},
        {"code": "B1", "meaning": "Accepted with comments", "suitability": "Construction with the noted comments resolved"},
    ],
    "cde_workflow.access_permissions": (
        "Permissions are granted by task team, not by individual. Each team has write access to its own "
        "volume in WIP, read access to everything in Shared, and no write access to Published. The facade "
        "contractor is granted read access to the concourse volume only. Permission changes are requested "
        "through the information manager and logged."
    ),
    "cde_workflow.archiving": (
        "Superseded containers are retained in the CDE archive for the contract period plus twelve years. "
        "At handover a full CDE export is delivered to the appointing party as an offline archive."
    ),

    "standards_methods.standards_adopted": [
        {"standard": "BS EN ISO 19650-1 and -2", "version": "2018", "application": "All information management"},
        {"standard": "BS EN ISO 19650-5", "version": "2020", "application": "Security-minded approach"},
        {"standard": "BS 8541 series", "version": "2012", "application": "Library object definition"},
        {"standard": "EN 17412-1", "version": "2020", "application": "Level of information need"},
    ],
    "standards_methods.classification": "Uniclass 2015 — tables Ss, Pr and EF applied to all modelled objects",
    "standards_methods.production_methods": (
        "Models are authored from the issued project templates, which carry the shared parameter file, the "
        "agreed view templates and the Uniclass mapping. Objects are modelled once and referenced, never "
        "copied between models. Drawings are produced from live model views; detached details are permitted "
        "only where the geometry is not modelled, and each such detail carries a note saying so. Every "
        "container is checked by its author against the pre-share checklist before the transition request, "
        "and the checklist output is attached to the container as evidence."
    ),
    "standards_methods.reference_material": [
        {"resource": "Phase 1 as-built survey", "source": "CTA Asset Management", "location": "CDE / Reference / Survey"},
        {"resource": "Registered point cloud (concourse)", "source": "Survey task team", "location": "CDE / Reference / Scans"},
        {"resource": "Operator CAFM data dictionary", "source": "P. Lindqvist", "location": "CDE / Reference / Asset"},
    ],

    "modelling_federation.model_breakdown": [
        {"model": "Concourse architecture", "discipline": "Architecture", "volume": "CN",
         "author": "S. Mbeki", "software": "Autodesk Revit"},
        {"model": "Viaduct structure", "discipline": "Structures", "volume": "EB",
         "author": "D. Ferreira", "software": "Autodesk Revit"},
        {"model": "Concourse services", "discipline": "MEP", "volume": "CN",
         "author": "H. Novak", "software": "Autodesk Revit"},
        {"model": "Highway and drainage", "discipline": "Civils", "volume": "ZZ",
         "author": "K. Adeyemi", "software": "Bentley OpenRoads"},
        {"model": "Federated coordination model", "discipline": "Coordination", "volume": "ZZ",
         "author": "M. Tanaka", "software": "Autodesk Navisworks"},
    ],
    "modelling_federation.coordinate_system": (
        "All models use OSGB36 grid with Newlyn datum. The shared origin is E 452100.000, N 245600.000, "
        "Z +12.500, set at the south-west corner of the concourse grid. Models are authored in millimetres "
        "and exported in metres. True north is 7.4 degrees east of project north and is recorded in every "
        "authoring template."
    ),
    "modelling_federation.federation_strategy": (
        "The coordination team federates by volume, not by discipline: the concourse federation and the "
        "viaduct federation are assembled separately and only combined for the gateway review, because the "
        "combined model exceeds the review workstation's practical limit. Federation is by reference, and "
        "no geometry is authored in the federated model."
    ),
    "modelling_federation.model_limits": (
        "Authoring models are split when they exceed 300 MB or 20 seconds to open. Linked models are "
        "loaded by worksets so reviewers can unload volumes they are not reviewing."
    ),

    "coordination_quality.coordination_cycle": (
        "The coordination cycle is weekly. Task teams share by Tuesday 16:00, the coordination team "
        "federates and runs the clash matrix on Wednesday, the clash report is issued Thursday morning, "
        "and the coordination meeting resolves priority issues Thursday afternoon. Issues not closed within "
        "two cycles are escalated to the delivery team meeting."
    ),
    "coordination_quality.clash_matrix": [
        {"test": "Services vs structure", "discipline_a": "MEP", "discipline_b": "Structures",
         "tolerance": "0 mm", "priority": "Critical"},
        {"test": "Services vs services", "discipline_a": "MEP", "discipline_b": "MEP",
         "tolerance": "25 mm", "priority": "High"},
        {"test": "Services vs ceiling void", "discipline_a": "MEP", "discipline_b": "Architecture",
         "tolerance": "50 mm", "priority": "Critical"},
        {"test": "Structure vs highway", "discipline_a": "Structures", "discipline_b": "Civils",
         "tolerance": "0 mm", "priority": "Critical"},
        {"test": "Maintenance access zones", "discipline_a": "MEP", "discipline_b": "Architecture",
         "tolerance": "0 mm", "priority": "Medium"},
    ],
    "coordination_quality.qa_checks": [
        {"check": "Model integrity", "method": "Navisworks audit plus template validation script",
         "responsible": "Task team manager", "frequency": "Before every share",
         "evidence": "Checklist PDF attached to the container"},
        {"check": "Standards compliance", "method": "Naming and classification validation script",
         "responsible": "CDE administrator", "frequency": "Before every share",
         "evidence": "Validation log stored with the container"},
        {"check": "Information content against LOIN", "method": "Parameter completeness report",
         "responsible": "Information manager", "frequency": "At each milestone",
         "evidence": "LOIN compliance report issued with the data drop"},
        {"check": "Asset data schema", "method": "Automated validation against CTA-AIR-002",
         "responsible": "Information manager", "frequency": "Per data drop",
         "evidence": "Schema validation report"},
    ],
    "coordination_quality.issue_management": (
        "Issues are raised as BCF in the CDE, assigned to a named individual with a due date, and carry a "
        "priority from the clash matrix. Critical issues must be resolved within one coordination cycle; "
        "high within two. Unresolved critical issues block a gateway."
    ),
    "coordination_quality.authorisation": (
        "The information manager reviews every container proposed for Published state against the pre-share "
        "evidence and the milestone acceptance criteria, then submits it to the appointing party's project "
        "information manager, who authorises with status A1 or returns it B1 with comments."
    ),

    "technology.software_stack": [
        {"purpose": "Architectural and MEP authoring", "software": "Autodesk Revit", "version": "2026.2",
         "used_by": "Architecture, Structures, Building services"},
        {"purpose": "Civil authoring", "software": "Bentley OpenRoads", "version": "2024 R3",
         "used_by": "Civils task team"},
        {"purpose": "Federation and clash", "software": "Autodesk Navisworks", "version": "2026",
         "used_by": "BIM coordination team"},
        {"purpose": "Common data environment", "software": "Autodesk Construction Cloud", "version": "Cloud",
         "used_by": "All task teams"},
        {"purpose": "4D sequencing", "software": "Synchro", "version": "2025", "used_by": "Construction planning"},
    ],
    "technology.exchange_formats": [
        {"exchange": "Coordination models", "format": "IFC 4", "schema": "Reference View 1.2",
         "validation": "IfcOpenShell validation script before share"},
        {"exchange": "Civil models (interim)", "format": "IFC 2x3", "schema": "Coordination View 2.0",
         "validation": "Manual check against the deviation D-01 conditions"},
        {"exchange": "Asset data", "format": "XLSX", "schema": "CTA-AIR-002 schema",
         "validation": "Automated schema validation"},
        {"exchange": "Issues", "format": "BCF 2.1", "schema": "—", "validation": "CDE native"},
    ],
    "technology.interoperability": (
        "The civils task team's IFC 2x3 export loses Uniclass classification on linear elements, so "
        "classification for those objects is carried in the asset data spreadsheet until the tool upgrade "
        "lands in July. This is deviation D-01 and is tracked as risk R-02."
    ),

    "collaboration.meetings": [
        {"meeting": "Coordination meeting", "frequency": "Weekly, Thursday",
         "chair": "M. Tanaka", "attendees": "Task team managers", "output": "Issue actions with owners and dates"},
        {"meeting": "Delivery team meeting", "frequency": "Fortnightly",
         "chair": "J. Salim", "attendees": "Task team leads, appointing party", "output": "MIDP status and escalations"},
        {"meeting": "Gateway review", "frequency": "Per gateway",
         "chair": "R. Okafor", "attendees": "Full delivery team and operator", "output": "Acceptance decision"},
        {"meeting": "Possession readiness review", "frequency": "Per possession",
         "chair": "Construction planning", "attendees": "Delivery team, site team", "output": "Go / no-go record"},
    ],
    "collaboration.communication_channels": (
        "Formal information moves through the CDE only; email is not an information exchange. Day-to-day "
        "queries use the project channel, and anything that changes a commitment in this plan is raised as "
        "a CDE comment so it is traceable. Escalation runs task team manager, information manager, then "
        "the appointing party's project information manager."
    ),

    "security.security_triage": "Sensitive — security-minded approach required",
    "security.classification_scheme": [
        {"classification": "Official — sensitive", "examples": "Electrical intake, signalling interface, CCTV layouts",
         "handling": "Named-individual access only, no download outside the CDE, watermarked issues"},
        {"classification": "Official", "examples": "General design information",
         "handling": "Delivery team access through the CDE"},
        {"classification": "Public", "examples": "Published visualisations approved by the client's comms team",
         "handling": "Released only through the appointing party"},
    ],
    "security.access_control": (
        "Access to the sensitive volume requires the appointing party's written approval per individual, is "
        "reviewed quarterly, and is revoked within one working day of a leaver notification. Third-party "
        "sharing of any sensitive container requires the appointing party's approval in advance."
    ),
    "security.incident_response": (
        "Suspected breaches are reported to the information manager and the appointing party's security "
        "lead within two hours, access is suspended pending review, and an incident record is kept."
    ),

    "handover.air_response": (
        "The operator's asset information requirements are met by a structured spreadsheet drop aligned to "
        "the CTA-AIR-002 schema at each of the three data drops, rather than a single handover. Asset tags "
        "are allocated by the operator's numbering service at Stage 4 so that the tag in the model is the "
        "tag in the CAFM, avoiding the re-keying that Phase 1 required."
    ),
    "handover.handover_deliverables": [
        {"deliverable": "Asset information model (native and IFC)", "format": "RVT + IFC4",
         "responsible": "Information manager", "milestone": "Handover"},
        {"deliverable": "Validated asset data set", "format": "XLSX per AIR schema",
         "responsible": "Information manager", "milestone": "Each data drop"},
        {"deliverable": "O&M documentation linked to asset tags", "format": "PDF + index",
         "responsible": "Construction team", "milestone": "Handover"},
        {"deliverable": "CDE archive export", "format": "Offline archive",
         "responsible": "CDE administrator", "milestone": "Handover"},
    ],
    "handover.cobie_strategy": (
        "COBie is not used. The operator's CAFM consumes the CTA-AIR-002 schema directly, and a COBie "
        "intermediate would lose the operator's own maintenance regime fields. The mapping from model "
        "parameters to the AIR schema is maintained by the information manager."
    ),

    "risk.risk_register": [
        {"risk": "Possession dates move and compress the coordination cycle", "impact": "High",
         "likelihood": "Medium", "mitigation": "MIDP re-baselined within five days of any programme change; gateway criteria unchanged",
         "owner": "J. Salim", "review_date": "2026-07-01"},
        {"risk": "Civils IFC 2x3 export loses classification", "impact": "Medium", "likelihood": "High",
         "mitigation": "Classification carried in asset data until the July tool upgrade (deviation D-01)",
         "owner": "K. Adeyemi", "review_date": "2026-07-15"},
        {"risk": "Facade contractor joins the CDE late", "impact": "High", "likelihood": "Medium",
         "mitigation": "Read access provisioned at appointment; interim exchange by controlled transmittal",
         "owner": "A. Byrne", "review_date": "2026-06-20"},
        {"risk": "Civils task team IFC competence gap", "impact": "Medium", "likelihood": "Medium",
         "mitigation": "Training scheduled before the Stage 4 data drop; export reviewed by coordination team until then",
         "owner": "M. Tanaka", "review_date": "2026-08-01"},
        {"risk": "Viaduct soffit survey incomplete", "impact": "High", "likelihood": "Medium",
         "mitigation": "Photogrammetry deviation proposed; decision required before Stage 4",
         "owner": "R. Okafor", "review_date": "2026-06-30"},
    ],

    "training.competence_assessment": (
        "Capability was assessed at tender against the appointing party's questionnaire. All task teams met "
        "the threshold except the civils team on IFC export competence, which is addressed below and tracked "
        "as risk R-04."
    ),
    "training.training_plan": [
        {"topic": "IFC export and validation for OpenRoads", "audience": "Civils task team",
         "provider": "Internal — M. Tanaka", "date": "2026-07-20"},
        {"topic": "CDE states and transition evidence", "audience": "All new starters",
         "provider": "Internal — A. Byrne", "date": "2026-06-05"},
    ],

    "approval.signatories": [
        {"name": "J. Salim", "role": "Information manager", "organisation": "Harbour & Slate Engineering", "date": "2026-05-18"},
        {"name": "R. Okafor", "role": "Project information manager", "organisation": "City Transport Authority", "date": "2026-05-20"},
    ],
}
