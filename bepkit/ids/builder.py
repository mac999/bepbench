"""Turn the plan's Level of Information Need table into a buildingSMART IDS.

The LOIN table states what each element must carry. IDS is the standard that
makes such a statement machine-checkable, so the two are the same information in
two forms — one for the reader, one for the checker. Exporting rather than
re-authoring keeps them from drifting apart.

What is exported is only as good as what the author wrote: a row naming no IFC
class is skipped and reported, never guessed into a silent false positive. The
same goes for a class the target schema does not define: IfcCourse exists only
in IFC4X3, and a specification aimed at IFC4 would match nothing and pass.

Every value written into the document comes from the ``ids`` settings block.
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

# The IFC grammar for a property set or property name: what the schema accepts,
# not a policy, so it is not a setting.
_IFC_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    narrowed: list[RowIssue] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    ifc_version: list[str] = field(default_factory=list)
    milestone: str = ""
    default_pset_properties: int = 0
    default_pset: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "specifications": self.specifications,
            "ifc_version": list(self.ifc_version),
            "milestone": self.milestone,
            "identifiers": list(self.identifiers),
            "default_pset_properties": self.default_pset_properties,
            "default_pset": self.default_pset,
            "skipped": [s.to_dict() for s in self.skipped],
            "inferred": [i.to_dict() for i in self.inferred],
            "narrowed": [n.to_dict() for n in self.narrowed],
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
    parts = re.split(setting("ids.property_split", r"[,;/]| and "), str(text or ""))
    out: list[str] = []
    for part in parts:
        name = re.sub(r"\s+", " ", part).strip(" .;:")
        if 2 <= len(name) <= 60:
            out.append(name)
    return out


def split_qualified(name: str) -> tuple[str | None, str]:
    """``"Pset_DoorCommon.FireRating"`` -> ``("Pset_DoorCommon", "FireRating")``.

    Only a name whose both halves are valid IFC names counts as qualified, so
    ordinary text such as ``"Rev. no"`` is left alone.
    """
    separator = setting("ids.pset_separator", ".") or "."
    if separator in name:
        pset, base = name.split(separator, 1)
        if _IFC_NAME.match(pset) and _IFC_NAME.match(base):
            return pset, base
    return None, name


def normalise_schema(name: str) -> str:
    """What a file header or a user typed, as the schema name IDS uses."""
    key = str(name or "").strip().upper()
    aliases = {str(k).upper(): v for k, v in (setting("ids.schema_aliases", {}) or {}).items()}
    return aliases.get(key, key)


def resolve_versions(versions: Any) -> list[str]:
    """A list of target schemas, normalised and de-duplicated in order."""
    if versions is None or versions == "" or versions == []:
        versions = setting("ids.ifc_version", ["IFC4"])
    if isinstance(versions, str):
        versions = [v for v in re.split(r"[,\s]+", versions) if v]
    out: list[str] = []
    for version in versions:
        name = normalise_schema(version)
        if name and name not in out:
            out.append(name)
    return out


def _schema(name: str):
    try:
        import ifcopenshell.ifcopenshell_wrapper as wrapper
    except ImportError:  # pragma: no cover - ifctester brings ifcopenshell
        return None
    try:
        return wrapper.schema_by_name(name)
    except Exception as exc:
        raise IdsError(f"unknown IFC schema '{name}'") from exc


def schemas_defining(ifc_class: str, versions: list[str]) -> list[str]:
    """The subset of ``versions`` in which ``ifc_class`` is an entity."""
    found: list[str] = []
    for version in versions:
        schema = _schema(version)
        if schema is None:  # no schema data available: cannot tell, so trust it
            return list(versions)
        try:
            declaration = schema.declaration_by_name(ifc_class)
        except Exception:
            continue
        if declaration.as_entity() is not None:
            found.append(version)
    return found


def milestone_column(framework_id: str) -> str:
    source = loin_source(framework_id)
    return (source.get("columns") or {}).get("stage", "stage")


def _milestone_key(value: str) -> tuple[float, str]:
    match = re.match(r"\s*(\d+(?:\.\d+)?)", value)
    return (float(match.group(1)) if match else float("inf"), value)


def milestones(framework_id: str, values: dict[str, dict[str, Any]]) -> list[str]:
    """The distinct milestones the LOIN table names, in natural order."""
    source = loin_source(framework_id)
    column = milestone_column(framework_id)
    rows = table_rows((values.get(source["section"]) or {}).get(source["field"]))
    seen = {str(row.get(column, "")).strip() for row in rows}
    return sorted((m for m in seen if m), key=_milestone_key)


def _pascal(text: str) -> str:
    """A property name IFC will accept: no spaces, no punctuation."""
    words = re.sub(r"[^A-Za-z0-9 ]", " ", text).split()
    return "".join(w[:1].upper() + w[1:] for w in words) or "Property"


def build(
    project: Any,
    framework: Any,
    values: dict[str, dict[str, Any]],
    *,
    ifc_version: Any = None,
    milestone: str | None = None,
    default_pset: str | None = None,
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

    milestone = str(milestone if milestone is not None else setting("ids.milestone", "")).strip()
    stage_column = columns.get("stage", "stage")
    if milestone:
        available = milestones(framework.id, values)
        if milestone.lower() not in {m.lower() for m in available}:
            raise IdsError(
                f"no row of the level of information need table is for milestone "
                f"'{milestone}' (the table names: {', '.join(available) or 'none'})."
            )

    versions = resolve_versions(ifc_version)
    for version in versions:
        _schema(version)  # fail early and clearly on a misspelt schema
    pset = default_pset or setting("ids.default_pset", "BEP_Requirements")
    data_type = setting("ids.data_type", "IFCLABEL")
    identifier_format = setting("ids.identifier_format", "LOIN-{index:03d}")

    document = ids_model.Ids(
        title=setting("ids.title_format", "{project}").format(
            project=project.name, framework=framework.name, milestone=milestone),
        copyright=project.client or "",
        version=str(setting("ids.document_version", "1.0")),
        description=setting("ids.description_format", "").format(
            project=project.name, framework=framework.name, milestone=milestone) or None,
        author=_author_email(project),
        date=date.today().isoformat(),
        purpose=project.reference or "BIM Execution Plan",
        milestone=milestone or (values.get("project_information") or {}).get("project_stage", ""),
    )

    classification = _classification_system(source, values)
    result = BuildResult(xml="", specifications=0, ifc_version=versions, milestone=milestone,
                         default_pset=pset)

    for index, row in enumerate(rows, start=1):
        element = str(row.get(columns.get("element", "element"), "")).strip()
        if not element:
            continue
        stage = str(row.get(stage_column, "")).strip()
        if milestone and stage.lower() != milestone.lower():
            continue

        declared = str(row.get(columns.get("ifc_class", "ifc_class"), "")).strip()
        ifc_class = declared or infer_ifc_class(element)
        if not ifc_class:
            result.skipped.append(RowIssue(index, element,
                                           "no IFC class declared and none could be inferred"))
            continue

        targets = schemas_defining(ifc_class, versions)
        if not targets:
            result.skipped.append(RowIssue(
                index, element, f"{ifc_class} is not defined in {', '.join(versions)}"))
            continue
        if not declared:
            result.inferred.append(RowIssue(index, element, f"inferred as {ifc_class}"))
        if len(targets) < len(versions):
            result.narrowed.append(RowIssue(
                index, element, f"{ifc_class} exists only in {', '.join(targets)}"))

        lod = str(row.get(columns.get("lod", "lod"), "")).strip()
        alphanumeric = str(row.get(columns.get("alphanumeric", "alphanumeric"), "")).strip()
        geometry = str(row.get(columns.get("geometry", "geometry"), "")).strip()

        identifier = identifier_format.format(index=index, milestone=stage)
        spec = ids_model.Specification(
            name=element[:100],
            ifcVersion=list(targets),
            identifier=identifier,
            description=" · ".join(p for p in (
                f"LOD {lod}" if lod else "", f"Stage {stage}" if stage else "", geometry
            ) if p) or None,
            instructions=alphanumeric or None,
            minOccurs=setting("ids.min_occurs", 0),
            maxOccurs=setting("ids.max_occurs", "unbounded"),
        )
        spec.applicability.append(ids_model.Entity(name=ifc_class.upper()))

        for attribute in setting("ids.required_attributes", ["Name"]) or []:
            spec.requirements.append(ids_model.Attribute(
                name=attribute, cardinality="required",
                instructions=f"Every element must carry {attribute}.",
            ))
        if classification:
            spec.requirements.append(ids_model.Classification(
                system=classification, cardinality="required",
                instructions=f"Classified under {classification}.",
            ))
        for name in split_properties(alphanumeric):
            qualified_set, base = split_qualified(name)
            if not qualified_set:
                result.default_pset_properties += 1
            spec.requirements.append(ids_model.Property(
                propertySet=qualified_set or pset,
                baseName=base if qualified_set else _pascal(name),
                dataType=data_type, cardinality="required",
                instructions=name,
            ))

        document.specifications.append(spec)
        result.identifiers.append(identifier)
        result.specifications += 1

    if not result.specifications:
        raise IdsError(
            "no row could be turned into a specification: none names an IFC class "
            f"defined in {', '.join(versions)}. Fill the IFC class column in the level "
            "of information need table, or target another schema."
        )

    result.xml = document.to_string()
    return result


def _author_email(project: Any) -> str:
    """IDS requires the author to be an email address."""
    owner = (getattr(project, "owner", "") or "").strip()
    if "@" in owner:
        return owner
    domain = setting("ids.author_domain", "example.com")
    slug = re.sub(r"[^a-z0-9]+", ".", owner.lower()).strip(".") or "information.manager"
    return f"{slug}@{domain}"


def _classification_system(source: dict[str, Any], values: dict[str, dict[str, Any]]) -> str:
    """The classification system named in the plan, e.g. "Uniclass 2015"."""
    where = source.get("classification") or {}
    if not where.get("section") or not where.get("field"):
        return ""
    text = str((values.get(where["section"]) or {}).get(where["field"], "")).strip()
    if not text:
        return ""
    head = re.split(setting("ids.classification_split", r"[—–\-,(]"), text)[0].strip()
    return head[: int(setting("ids.classification_max_length", 60))]


def validate_against(xml: str, ifc_path: str,
                     identifiers: list[str] | None = None) -> dict[str, Any]:
    """Run the generated IDS against a real IFC and summarise the outcome."""
    _require()
    import tempfile
    from pathlib import Path

    import ifcopenshell

    identifiers = identifiers or []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.ids"
        path.write_text(xml, encoding="utf-8")
        document = ids_model.open(str(path))
        model = ifcopenshell.open(ifc_path)
        document.validate(model)

        specifications = []
        counts = {"passed": 0, "failed": 0, "not_applicable": 0}
        # ifctester does not keep the identifier when it re-reads a file, so the
        # report takes it from the build, in document order.
        for index, spec in enumerate(document.specifications):
            applicable = len(spec.applicable_entities)
            failures = len(spec.failed_entities)
            ok = bool(spec.status) and failures == 0
            # An optional specification with nothing to apply to passes in IDS,
            # but it has checked nothing, so it is not counted as satisfied.
            status = "failed" if not ok else "passed" if applicable else "not_applicable"
            counts[status] += 1
            specifications.append({
                "name": spec.name,
                "identifier": spec.identifier or (
                    identifiers[index] if index < len(identifiers) else str(index + 1)),
                "applicable": applicable,
                "failures": failures,
                "passed": status == "passed",
                "status": status,
            })

    return {"specifications": len(specifications), **counts, "results": specifications}
