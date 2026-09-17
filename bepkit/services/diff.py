"""Compare two versions of a plan.

A BEP is re-issued, not written once. The question a reviewer actually asks is
"what changed between P02 and C01, and did the score move because the plan got
better or because someone deleted a section". Snapshots already hold the whole
answer set, so a diff is a comparison, not new bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..scoring.rules import table_rows
from ..schema.models import Framework

ADDED, REMOVED, CHANGED, UNCHANGED = "added", "removed", "changed", "unchanged"


def _normalise(value: Any) -> Any:
    if isinstance(value, list):
        return [{k: str(v or "").strip() for k, v in row.items()}
                for row in table_rows(value)] if value and isinstance(value[0], dict) \
            else [str(v).strip() for v in value]
    if value is None:
        return ""
    return str(value).strip()


def _words(value: Any) -> int:
    return len(str(value or "").split())


@dataclass
class FieldChange:
    section_id: str
    section_title: str
    field_id: str
    label: str
    type: str
    status: str
    before: Any = None
    after: Any = None
    detail: str = ""

    @property
    def path(self) -> str:
        return f"{self.section_id}.{self.field_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path, "section": self.section_id,
            "section_title": self.section_title, "field": self.field_id,
            "label": self.label, "type": self.type, "status": self.status,
            "detail": self.detail,
            "before": self.before, "after": self.after,
        }


@dataclass
class SectionDiff:
    id: str
    title: str
    changes: list[FieldChange] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0

    @property
    def score_delta(self) -> float:
        return self.score_after - self.score_before

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title,
            "score_before": round(self.score_before, 1),
            "score_after": round(self.score_after, 1),
            "score_delta": round(self.score_delta, 1),
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class PlanDiff:
    label_before: str
    label_after: str
    score_before: float
    score_after: float
    sections: list[SectionDiff] = field(default_factory=list)

    @property
    def score_delta(self) -> float:
        return self.score_after - self.score_before

    def counts(self) -> dict[str, int]:
        out = {ADDED: 0, REMOVED: 0, CHANGED: 0}
        for section in self.sections:
            for change in section.changes:
                out[change.status] = out.get(change.status, 0) + 1
        return out

    @property
    def total_changes(self) -> int:
        return sum(self.counts().values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": {"label": self.label_before, "score": round(self.score_before, 1)},
            "after": {"label": self.label_after, "score": round(self.score_after, 1)},
            "score_delta": round(self.score_delta, 1),
            "counts": self.counts(),
            "total_changes": self.total_changes,
            "sections": [s.to_dict() for s in self.sections],
        }


def _describe(field_type: str, before: Any, after: Any) -> str:
    """One line saying how the answer moved, in the field's own terms."""
    if field_type == "table":
        n_before, n_after = len(before or []), len(after or [])
        if n_before != n_after:
            verb = "added" if n_after > n_before else "removed"
            return f"{abs(n_after - n_before)} row(s) {verb} ({n_before} → {n_after})"
        return "cell values edited"
    if field_type in ("markdown", "textarea"):
        w_before, w_after = _words(before), _words(after)
        if w_before != w_after:
            return f"{w_before} → {w_after} words"
        return "rewritten"
    return f"“{str(before)[:40]}” → “{str(after)[:40]}”"


def compare(
    framework: Framework,
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    *,
    label_before: str = "before",
    label_after: str = "after",
    stage: str | None = None,
    include_unchanged: bool = False,
) -> PlanDiff:
    """Diff two answer sets field by field, scoring each side as it goes."""
    from ..scoring import evaluate

    report_before = evaluate(framework, before, stage=stage)
    report_after = evaluate(framework, after, stage=stage)

    diff = PlanDiff(
        label_before=label_before, label_after=label_after,
        score_before=report_before.score, score_after=report_after.score,
    )

    for section in framework.sections_for(stage):
        before_section = before.get(section.id) or {}
        after_section = after.get(section.id) or {}
        entry = SectionDiff(
            id=section.id, title=section.title,
            score_before=(report_before.section(section.id).score
                          if report_before.section(section.id) else 0.0),
            score_after=(report_after.section(section.id).score
                         if report_after.section(section.id) else 0.0),
        )

        for f in section.fields_for(stage):
            old, new = _normalise(before_section.get(f.id)), _normalise(after_section.get(f.id))
            empty_old, empty_new = old in ("", [], None), new in ("", [], None)

            if empty_old and empty_new:
                status = UNCHANGED
            elif empty_old:
                status = ADDED
            elif empty_new:
                status = REMOVED
            elif old == new:
                status = UNCHANGED
            else:
                status = CHANGED

            if status == UNCHANGED and not include_unchanged:
                continue

            entry.changes.append(FieldChange(
                section_id=section.id, section_title=section.title,
                field_id=f.id, label=f.label, type=f.type, status=status,
                before=old, after=new,
                detail=_describe(f.type, old, new) if status == CHANGED else "",
            ))

        if entry.changes or abs(entry.score_delta) >= 0.05:
            diff.sections.append(entry)

    return diff


def compare_snapshots(project: Any, before: Any, after: Any, **kwargs: Any) -> PlanDiff:
    """Diff two snapshots of one plan."""
    from .projects import framework_for

    return compare(
        framework_for(project),
        (before.data or {}).get("values") or {},
        (after.data or {}).get("values") or {},
        label_before=before.label or f"#{before.id}",
        label_after=after.label or f"#{after.id}",
        stage=project.stage or None,
        **kwargs,
    )


def compare_snapshot_to_current(project: Any, snapshot: Any, **kwargs: Any) -> PlanDiff:
    """Diff a snapshot against what the plan says now."""
    from .projects import framework_for

    return compare(
        framework_for(project),
        (snapshot.data or {}).get("values") or {},
        project.values(),
        label_before=snapshot.label or f"#{snapshot.id}",
        label_after="current",
        stage=project.stage or None,
        **kwargs,
    )
