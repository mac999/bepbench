"""Turn the plan's Level of Information Need table into a buildingSMART IDS.

The LOIN table states what each element must carry. IDS is the standard that
makes such a statement machine-checkable, so the two are the same information in
two forms — one for the reader, one for the checker. Exporting rather than
re-authoring keeps them from drifting apart.

What is exported is only as good as what the author wrote: a row naming no IFC
class is skipped and reported, never guessed into a silent false positive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..scoring.rules import table_rows
from ..settings import get as setting

try:
    from ifctester import ids as ids_model

    IFCTESTER_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    IFCTESTER_AVAILABLE = False


class IdsError(RuntimeError):
    """Raised for conditions the author needs to be told about."""


@dataclass
class RowIssue:
    row: int
    element: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"row": self.row, "element": self.element, "reason": self.reason}


@dataclass
class BuildResult:
    xml: str
    specifications: int
    skipped: list[RowIssue] = field(default_factory=list)
    inferred: list[RowIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "specifications": self.specifications,
            "skipped": [s.to_dict() for s in self.skipped],
            "inferred": [i.to_dict() for i in self.inferred],
        }


def _require():
    if not IFCTESTER_AVAILABLE:
        raise IdsError(
            "IDS export needs the optional 'ifctester' package (pip install ifctester)."
        )


def loin_source(framework_id: str) -> dict[str, Any]:
    """Which table in this framework holds the level of information need."""
    mapping = setting("ids.sources", {}) or {}
    source = mapping.get(framework_id)
    if not source:
        raise IdsError(
            f"no IDS mapping for framework '{framework_id}'. "
            "Add one under ids.sources in the settings file."
        )
    return source


def infer_ifc_class(text: str) -> str | None:
    """Best-effort IFC class from an element name, using the configured hints."""
    needle = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    words = set(needle.split())
    best: tuple[int, str] | None = None
    for keyword, ifc_class in (setting("ids.class_hints", {}) or {}).items():
        key = keyword.lower()
        hit = key in words if " " not in key else key in needle
        if hit and (best is None or len(key) > best[0]):
            best = (len(key), ifc_class)
    return best[1] if best else None


def split_properties(text: str) -> list[str]:
    """Split an alphanumeric requirement into individual property names."""
    parts = re.split(r"[,;/]| and ", str(text or ""))
    out: list[str] = []
    for part in parts:
        name = re.sub(r"\s+", " ", part).strip(" .;:")
        if 2 <= len(name) <= 60:
            out.append(name)
    return out


def _pascal(text: str) -> str:
    """A property name IFC will accept: no spaces, no punctuation."""
    words = re.sub(r"[^A-Za-z0-9 ]", " ", text).split()
    return "".join(w[:1].upper() + w[1:] for w in words) or "Property"


def build(
    project: Any,
    framework: Any,
    values: dict[str, dict[str, Any]],
    *,
    ifc_version: str | None = None,
) -> BuildResult:
    """Build an IDS document from the plan's LOIN table."""
    _require()

    source = loin_source(framework.id)
    section_id, field_id = source["section"], source["field"]
    columns = source.get("columns", {})
    rows = table_rows((values.get(section_id) or {}).get(field_id))
    if not rows:
        raise IdsError(
            "the plan's level of information need table is empty, so there is "
            "nothing to specify."
        )

    versions = ifc_version or setting("ids.ifc_version", ["IFC4"])
    if isinstance(versions, str):
        versions = [versions]
    pset = setting("ids.default_pset", "BEP_Requirements")

    document = ids_model.Ids(
        title=f"{project.name} — Level of Information Need",
        copyright=project.client or "",
        version="1.0",
        description=f"Generated from the BIM Execution Plan ({framework.name}).",
        author=_author_email(project),
        date=date.today().isoformat(),
        purpose=project.reference or "BIM Execution Plan",
        milestone=(values.get("project_information") or {}).get("project_stage", ""),
    )

    classification = _classification_system(values)
    skipped: list[RowIssue] = []
    inferred: list[RowIssue] = []
    count = 0

    for index, row in enumerate(rows, start=1):
        element = str(row.get(columns.get("element", "element"), "")).strip()
        if not element:
            continue

        declared = str(row.get(columns.get("ifc_class", "ifc_class"), "")).strip()
        ifc_class = declared or infer_ifc_class(element)
        if not ifc_class:
            skipped.append(RowIssue(index, element,
                                    "no IFC class declared and none could be inferred"))
            continue
        if not declared:
            inferred.append(RowIssue(index, element, f"inferred as {ifc_class}"))

        lod = str(row.get(columns.get("lod", "lod"), "")).strip()
        stage = str(row.get(columns.get("stage", "stage"), "")).strip()
        alphanumeric = str(row.get(columns.get("alphanumeric", "alphanumeric"), "")).strip()
        geometry = str(row.get(columns.get("geometry", "geometry"), "")).strip()

        spec = ids_model.Specification(
            name=element[:100],
            ifcVersion=list(versions),
            identifier=f"LOIN-{index:03d}",
            description=" · ".join(p for p in (
                f"LOD {lod}" if lod else "", f"Stage {stage}" if stage else "", geometry
            ) if p) or None,
            instructions=alphanumeric or None,
            minOccurs=0,
            maxOccurs="unbounded",
        )
        spec.applicability.append(ids_model.Entity(name=ifc_class.upper()))

        # Every element must be identifiable; that is the floor of any LOIN.
        spec.requirements.append(ids_model.Attribute(
            name="Name", cardinality="required",
            instructions="Every element must carry a name.",
        ))
        if classification:
            spec.requirements.append(ids_model.Classification(
                system=classification, cardinality="required",
                instructions=f"Classified under {classification}.",
            ))
        for name in split_properties(alphanumeric):
            spec.requirements.append(ids_model.Property(
                propertySet=pset, baseName=_pascal(name),
                dataType="IFCLABEL", cardinality="required",
                instructions=name,
            ))

        document.specifications.append(spec)
        count += 1

    if not count:
        raise IdsError(
            "no row could be turned into a specification: none names an IFC class. "
            "Fill the IFC class column in the level of information need table."
        )

    return BuildResult(xml=document.to_string(), specifications=count,
                       skipped=skipped, inferred=inferred)


def _author_email(project: Any) -> str:
    """IDS requires the author to be an email address."""
    owner = (getattr(project, "owner", "") or "").strip()
    if "@" in owner:
        return owner
    domain = setting("ids.author_domain", "example.com")
    slug = re.sub(r"[^a-z0-9]+", ".", owner.lower()).strip(".") or "information.manager"
    return f"{slug}@{domain}"


def _classification_system(values: dict[str, dict[str, Any]]) -> str:
    for section_id, field_id in (("standards_methods", "classification"),
                                 ("model_standards", "classification")):
        text = str((values.get(section_id) or {}).get(field_id, "")).strip()
        if text:
            # "Uniclass 2015 — tables Ss, Pr…" → "Uniclass 2015"
            return re.split(r"[—–\-,(]", text)[0].strip()[:60]
    return ""


def validate_against(xml: str, ifc_path: str) -> dict[str, Any]:
    """Run the generated IDS against a real IFC and summarise the outcome."""
    _require()
    import tempfile
    from pathlib import Path

    import ifcopenshell

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.ids"
        path.write_text(xml, encoding="utf-8")
        document = ids_model.open(str(path))
        model = ifcopenshell.open(ifc_path)
        document.validate(model)

        specifications = []
        passed = failed = 0
        # ifctester does not keep the identifier when it re-reads a file, so the
        # report numbers the specifications itself rather than showing None.
        for index, spec in enumerate(document.specifications, start=1):
            applicable = len(spec.applicable_entities)
            failures = len(spec.failed_entities)
            ok = bool(spec.status) and failures == 0
            passed += 1 if ok else 0
            failed += 0 if ok else 1
            specifications.append({
                "name": spec.name,
                "identifier": spec.identifier or f"LOIN-{index:03d}",
                "applicable": applicable,
                "failures": failures,
                "passed": ok,
            })

    return {
        "specifications": len(specifications),
        "passed": passed,
        "failed": failed,
        "results": specifications,
    }
