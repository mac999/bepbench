"""Dataclasses describing a BEP framework (template definition).

A *framework* is a versioned, declarative description of what a BIM Execution
Plan must contain. It is data, not code: frameworks live as YAML files in
``bepkit/frameworks`` so that a BIM manager can add a house standard without
touching the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


FIELD_TYPES = {
    "text",
    "textarea",
    "markdown",
    "number",
    "date",
    "select",
    "multiselect",
    "list",
    "boolean",
    "table",
    "link",
}


def _stages(raw: Any) -> tuple[str, ...]:
    """Normalise a stage declaration; an unknown stage name is a framework bug."""
    if not raw:
        return ()
    values = [raw] if isinstance(raw, str) else list(raw)
    for value in values:
        if value not in STAGES:
            raise ValueError(f"unknown stage {value!r} (use: {', '.join(STAGES)})")
    return tuple(values)


@dataclass(frozen=True)
class Column:
    """One column of a ``table`` field."""

    id: str
    label: str
    type: str = "text"
    required: bool = False
    options: list[str] = field(default_factory=list)
    help: str = ""
    width: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Column":
        return cls(
            id=raw["id"],
            label=raw.get("label", raw["id"].replace("_", " ").title()),
            type=raw.get("type", "text"),
            required=bool(raw.get("required", False)),
            options=list(raw.get("options", [])),
            help=raw.get("help", ""),
            width=raw.get("width", ""),
        )


@dataclass(frozen=True)
class Quality:
    """Depth expectations used by the scoring engine.

    ``min_words`` applies to prose fields, ``min_rows`` to tables and
    ``min_items`` to list/multiselect fields. A field that is merely present
    scores a partial credit; full credit needs the expected depth.
    """

    min_words: int = 0
    min_rows: int = 0
    min_items: int = 0
    evidence: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Quality":
        return cls(
            min_words=int(raw.get("min_words", 0)),
            min_rows=int(raw.get("min_rows", 0)),
            min_items=int(raw.get("min_items", 0)),
            evidence=bool(raw.get("evidence", False)),
        )


STAGES = ("pre_appointment", "delivery")


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    type: str = "text"
    required: bool = False
    weight: float = 1.0
    help: str = ""
    placeholder: str = ""
    example: str = ""
    reference: str = ""
    options: list[str] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)
    quality: Quality = field(default_factory=Quality)
    # Which appointment stages ask for this field. Empty means every stage.
    stages: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Field":
        ftype = raw.get("type", "text")
        if ftype not in FIELD_TYPES:
            raise ValueError(f"unknown field type {ftype!r} for field {raw.get('id')!r}")
        return cls(
            id=raw["id"],
            label=raw.get("label", raw["id"].replace("_", " ").title()),
            type=ftype,
            required=bool(raw.get("required", False)),
            weight=float(raw.get("weight", 1.0)),
            help=raw.get("help", ""),
            placeholder=raw.get("placeholder", ""),
            example=raw.get("example", ""),
            reference=raw.get("reference", ""),
            options=list(raw.get("options", [])),
            columns=[Column.from_dict(c) for c in raw.get("columns", [])],
            quality=Quality.from_dict(raw.get("quality", {})),
            stages=_stages(raw.get("stages")),
        )

    @property
    def is_tabular(self) -> bool:
        return self.type == "table"

    def in_stage(self, stage: str | None) -> bool:
        return not stage or not self.stages or stage in self.stages


@dataclass(frozen=True)
class Check:
    """A declarative cross-field consistency rule.

    Checks are evaluated by named handlers in :mod:`bepkit.scoring.rules`;
    ``params`` carries whatever that handler needs.
    """

    id: str
    rule: str
    message: str
    severity: str = "major"
    section: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    fix: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Check":
        known = {"id", "rule", "message", "severity", "section", "fix"}
        return cls(
            id=raw["id"],
            rule=raw["rule"],
            message=raw.get("message", raw["id"]),
            severity=raw.get("severity", "major"),
            section=raw.get("section", ""),
            fix=raw.get("fix", ""),
            params={k: v for k, v in raw.items() if k not in known},
        )


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    order: int = 0
    weight: float = 1.0
    intent: str = ""
    guidance: str = ""
    reference: str = ""
    icon: str = ""
    fields: list[Field] = field(default_factory=list)
    stages: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any], order: int) -> "Section":
        return cls(
            id=raw["id"],
            title=raw.get("title", raw["id"].replace("_", " ").title()),
            order=int(raw.get("order", order)),
            weight=float(raw.get("weight", 1.0)),
            intent=raw.get("intent", ""),
            guidance=raw.get("guidance", ""),
            reference=raw.get("reference", ""),
            icon=raw.get("icon", ""),
            fields=[Field.from_dict(f) for f in raw.get("fields", [])],
            stages=_stages(raw.get("stages")),
        )

    def in_stage(self, stage: str | None) -> bool:
        return not stage or not self.stages or stage in self.stages

    def fields_for(self, stage: str | None) -> list[Field]:
        return [f for f in self.fields if f.in_stage(stage)]

    def field_by_id(self, field_id: str) -> Field | None:
        for f in self.fields:
            if f.id == field_id:
                return f
        return None


@dataclass(frozen=True)
class Framework:
    id: str
    name: str
    version: str = "1.0"
    description: str = ""
    reference: str = ""
    maturity_bands: list[dict[str, Any]] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Framework":
        sections = [Section.from_dict(s, i * 10) for i, s in enumerate(raw.get("sections", []))]
        sections.sort(key=lambda s: s.order)
        fw = cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            version=str(raw.get("version", "1.0")),
            description=raw.get("description", ""),
            reference=raw.get("reference", ""),
            maturity_bands=list(raw.get("maturity_bands", [])),
            sections=sections,
            checks=[Check.from_dict(c) for c in raw.get("checks", [])],
        )
        fw.validate()
        return fw

    def validate(self) -> None:
        seen: set[str] = set()
        for section in self.sections:
            if section.id in seen:
                raise ValueError(f"duplicate section id {section.id!r} in framework {self.id!r}")
            seen.add(section.id)
            field_ids: set[str] = set()
            for f in section.fields:
                if f.id in field_ids:
                    raise ValueError(f"duplicate field id {section.id}.{f.id}")
                field_ids.add(f.id)
                if f.type in ("select", "multiselect") and not f.options:
                    raise ValueError(f"{section.id}.{f.id}: {f.type} needs options")
                if f.is_tabular and not f.columns:
                    raise ValueError(f"{section.id}.{f.id}: table needs columns")
        for check in self.checks:
            if check.section and not self.section_by_id(check.section):
                raise ValueError(f"check {check.id!r} points at unknown section {check.section!r}")

    def section_by_id(self, section_id: str) -> Section | None:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None

    def iter_fields(self, stage: str | None = None) -> Iterator[tuple[Section, Field]]:
        for section in self.sections:
            if not section.in_stage(stage):
                continue
            for f in section.fields:
                if f.in_stage(stage):
                    yield section, f

    def sections_for(self, stage: str | None = None) -> list[Section]:
        return [s for s in self.sections if s.in_stage(stage)]

    def resolve(self, path: str) -> tuple[Section, Field] | None:
        """Resolve a ``section.field`` dotted path."""
        if "." not in path:
            return None
        section_id, field_id = path.split(".", 1)
        section = self.section_by_id(section_id)
        if not section:
            return None
        f = section.field_by_id(field_id)
        return (section, f) if f else None

    @property
    def total_fields(self) -> int:
        return sum(len(s.fields) for s in self.sections)

    def fields_in_stage(self, stage: str | None) -> int:
        return sum(1 for _ in self.iter_fields(stage))
