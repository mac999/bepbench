"""Aggregation of field scores into a project-level BEP quality report.

Three numbers describe a plan, and they answer different questions:

``coverage``          How much of the template has been touched at all?
``required_coverage`` Are the mandatory commitments answered?
``score``             Weighted depth — is what is written actually usable?

Coverage rises quickly and flatters a draft; the score does not. Keeping them
separate is what stops the tool from rewarding box-ticking.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from typing import Any

from ..schema.models import Framework, Section
from ..settings import get as setting
from .rules import FieldScore, Issue, run_checks, score_field

SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}

DEFAULT_BANDS = [
    {"min": 0, "label": "Initial", "note": "Not yet a usable plan."},
    {"min": 25, "label": "Drafted", "note": "Structure present, substance missing."},
    {"min": 45, "label": "Defined", "note": "Core commitments written."},
    {"min": 65, "label": "Managed", "note": "Auditable and submission ready."},
    {"min": 85, "label": "Optimised", "note": "Complete and evidenced."},
]

# Overall score at or above this, with no blockers, means the plan can be issued.
# Both thresholds are site-configurable in the JSON settings.
READY_SCORE = float(setting("scoring.ready_score", 65.0))
READY_REQUIRED_COVERAGE = float(setting("scoring.ready_required_coverage", 90.0))


@dataclass
class SectionScore:
    id: str
    title: str
    weight: float
    score: float              # 0-100 weighted depth
    coverage: float           # 0-100 fields with any content
    required_total: int
    required_complete: int
    fields: list[FieldScore] = dc_field(default_factory=list)
    icon: str = ""

    @property
    def state(self) -> str:
        if self.score >= 85:
            return "complete"
        if self.score >= 45:
            return "progress"
        if self.score > 0:
            return "started"
        return "empty"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "icon": self.icon,
            "weight": self.weight,
            "score": round(self.score, 1),
            "coverage": round(self.coverage, 1),
            "state": self.state,
            "required_total": self.required_total,
            "required_complete": self.required_complete,
            "fields": [f.to_dict() for f in self.fields],
        }


@dataclass
class Recommendation:
    path: str
    section_id: str
    section_title: str
    label: str
    detail: str
    points: float             # overall points recoverable by completing this field

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "section": self.section_id,
            "section_title": self.section_title,
            "label": self.label,
            "detail": self.detail,
            "points": round(self.points, 2),
        }


@dataclass
class ScoreReport:
    framework_id: str
    framework_name: str
    score: float
    coverage: float
    required_coverage: float
    maturity_level: int
    maturity_label: str
    maturity_note: str
    next_band: dict[str, Any] | None
    stage: str | None
    sections: list[SectionScore]
    issues: list[Issue]
    recommendations: list[Recommendation]
    generated_at: str
    fields_total: int
    fields_filled: int

    @property
    def blockers(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "blocker"]

    @property
    def is_ready(self) -> bool:
        return (
            not self.blockers
            and self.score >= READY_SCORE
            and self.required_coverage >= READY_REQUIRED_COVERAGE
        )

    def issue_counts(self) -> dict[str, int]:
        counts = {"blocker": 0, "major": 0, "minor": 0, "info": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts

    def section(self, section_id: str) -> SectionScore | None:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": {"id": self.framework_id, "name": self.framework_name},
            "stage": self.stage,
            "score": round(self.score, 1),
            "coverage": round(self.coverage, 1),
            "required_coverage": round(self.required_coverage, 1),
            "maturity": {
                "level": self.maturity_level,
                "label": self.maturity_label,
                "note": self.maturity_note,
                "next": self.next_band,
            },
            "ready_to_issue": self.is_ready,
            "fields": {"total": self.fields_total, "filled": self.fields_filled},
            "issue_counts": self.issue_counts(),
            "sections": [s.to_dict() for s in self.sections],
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "generated_at": self.generated_at,
        }


def _bands(framework: Framework) -> list[dict[str, Any]]:
    bands = framework.maturity_bands or DEFAULT_BANDS
    return sorted(bands, key=lambda b: b.get("min", 0))


def _maturity(framework: Framework, score: float) -> tuple[int, str, str, dict[str, Any] | None]:
    bands = _bands(framework)
    level, current = 0, bands[0]
    for index, band in enumerate(bands):
        if score >= band.get("min", 0):
            level, current = index, band
    nxt = bands[level + 1] if level + 1 < len(bands) else None
    if nxt is not None:
        nxt = {"label": nxt.get("label", ""), "min": nxt.get("min", 0),
               "gap": round(nxt.get("min", 0) - score, 1), "note": nxt.get("note", "")}
    return level, current.get("label", ""), current.get("note", ""), nxt


def _score_section(section: Section, values: dict[str, Any],
                   stage: str | None = None) -> SectionScore:
    section_values = values.get(section.id) or {}
    fields = section.fields_for(stage)
    field_scores = [score_field(section.id, f, section_values.get(f.id)) for f in fields]
    total_weight = sum(f.weight for f in fields) or 1.0
    weighted = sum(fs.score * fs.weight for fs in field_scores)
    required = [fs for fs in field_scores if fs.required]
    return SectionScore(
        id=section.id,
        title=section.title,
        icon=section.icon,
        weight=section.weight,
        score=100.0 * weighted / total_weight,
        coverage=100.0 * sum(1 for fs in field_scores if fs.filled) / (len(field_scores) or 1),
        required_total=len(required),
        required_complete=sum(1 for fs in required if fs.score >= 0.999),
        fields=field_scores,
    )


def evaluate(framework: Framework, values: dict[str, Any], *,
             max_recommendations: int = 8, stage: str | None = None) -> ScoreReport:
    """Score ``values`` against ``framework`` and return a full report.

    ``stage`` restricts scoring to the fields that appointment stage asks for, so
    a pre-appointment BEP is not marked down for lacking detail that only exists
    after the appointment.
    """
    values = values or {}
    framework_sections = framework.sections_for(stage)
    sections = [_score_section(s, values, stage) for s in framework_sections]

    total_weight = sum(s.weight for s in framework_sections) or 1.0
    overall = sum(s.score * s.weight for s in sections) / total_weight

    all_fields = [fs for s in sections for fs in s.fields]
    filled = sum(1 for fs in all_fields if fs.filled)
    coverage = 100.0 * filled / (len(all_fields) or 1)
    required_fields = [fs for fs in all_fields if fs.required]
    required_coverage = (
        100.0 * sum(1 for fs in required_fields if fs.score >= 0.999) / len(required_fields)
        if required_fields else 100.0
    )

    issues = run_checks(framework, values)

    # Unanswered required fields are issues in their own right.
    for section_score, section in zip(sections, framework_sections):
        for fs in section_score.fields:
            if fs.required and fs.score < 0.999:
                issues.append(Issue(
                    id=f"required:{fs.path}",
                    severity="blocker" if not fs.filled else "minor",
                    message=(f"Required field “{fs.label}” is not answered."
                             if not fs.filled else
                             f"Required field “{fs.label}” is only partly answered."),
                    section_id=section.id,
                    section_title=section.title,
                    field_id=fs.field_id,
                    detail=fs.detail,
                    source="field",
                ))

    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.section_id, i.id))

    # Rank the remaining work by how many overall points each field is worth.
    recommendations: list[Recommendation] = []
    for section_score, section in zip(sections, framework_sections):
        section_field_weight = sum(f.weight for f in section.fields_for(stage)) or 1.0
        for fs in section_score.fields:
            if fs.score >= 0.999:
                continue
            points = (1.0 - fs.score) * fs.weight / section_field_weight * section.weight / total_weight * 100.0
            recommendations.append(Recommendation(
                path=fs.path,
                section_id=section.id,
                section_title=section.title,
                label=fs.label,
                detail=fs.detail or "Not answered.",
                points=points,
            ))
    recommendations.sort(key=lambda r: r.points, reverse=True)

    level, label, note, nxt = _maturity(framework, overall)
    return ScoreReport(
        framework_id=framework.id,
        framework_name=framework.name,
        score=overall,
        coverage=coverage,
        required_coverage=required_coverage,
        maturity_level=level,
        maturity_label=label,
        maturity_note=note,
        next_band=nxt,
        stage=stage,
        sections=sections,
        issues=issues,
        recommendations=recommendations[:max_recommendations],
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        fields_total=len(all_fields),
        fields_filled=filled,
    )
