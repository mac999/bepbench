"""Render a project as a Markdown BEP document."""

from __future__ import annotations

from typing import Any

from ..models import Project
from ..schema.models import Field, Framework
from ..scoring import ScoreReport
from ..scoring.rules import table_rows


def _escape_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip() or "—"


def render_field(field: Field, value: Any) -> str:
    if value is None or value == "" or value == []:
        return "_Not yet completed._"

    if field.type == "table":
        rows = table_rows(value)
        if not rows:
            return "_Not yet completed._"
        header = "| " + " | ".join(c.label for c in field.columns) + " |"
        divider = "| " + " | ".join("---" for _ in field.columns) + " |"
        body = [
            "| " + " | ".join(_escape_cell(row.get(c.id)) for c in field.columns) + " |"
            for row in rows
        ]
        return "\n".join([header, divider, *body])

    if field.type in ("multiselect", "list"):
        items = value if isinstance(value, list) else [value]
        return "\n".join(f"- {item}" for item in items if str(item).strip())

    if field.type == "boolean":
        return "Yes" if value else "No"

    return str(value).strip()


def render(project: Project, framework: Framework, report: ScoreReport, *, include_score: bool = True) -> str:
    values = project.values()
    out: list[str] = []
    out.append(f"# BIM Execution Plan — {project.name}")
    out.append("")
    out.append(f"**Framework:** {framework.name} (v{framework.version})  ")
    if project.client:
        out.append(f"**Appointing party:** {project.client}  ")
    if project.reference:
        out.append(f"**Project reference:** {project.reference}  ")
    out.append(f"**Status:** {project.status}  ")
    out.append(f"**Generated:** {report.generated_at}")
    out.append("")

    if include_score:
        counts = report.issue_counts()
        out.append("## Completeness Assessment")
        out.append("")
        out.append("| Metric | Value |")
        out.append("| --- | --- |")
        out.append(f"| BEP score | **{report.score:.1f} / 100** |")
        out.append(f"| Maturity | {report.maturity_label} — {report.maturity_note} |")
        out.append(f"| Template coverage | {report.coverage:.1f}% |")
        out.append(f"| Required fields answered | {report.required_coverage:.1f}% |")
        out.append(f"| Open issues | {counts['blocker']} blocking, {counts['major']} major, {counts['minor']} minor |")
        out.append(f"| Ready to issue | {'Yes' if report.is_ready else 'No'} |")
        out.append("")
        out.append("| Section | Score | Coverage |")
        out.append("| --- | ---: | ---: |")
        for section in report.sections:
            out.append(f"| {section.title} | {section.score:.0f} | {section.coverage:.0f}% |")
        out.append("")

    out.append("## Contents")
    out.append("")
    for index, section in enumerate(framework.sections, start=1):
        out.append(f"{index}. {section.title}")
    out.append("")

    for index, section in enumerate(framework.sections, start=1):
        out.append(f"## {index}. {section.title}")
        out.append("")
        if section.reference:
            out.append(f"> Reference: {section.reference}")
            out.append("")
        if section.intent:
            out.append(f"_{section.intent}_")
            out.append("")
        section_values = values.get(section.id) or {}
        for field in section.fields:
            marker = " *(required)*" if field.required else ""
            out.append(f"### {field.label}{marker}")
            out.append("")
            out.append(render_field(field, section_values.get(field.id)))
            out.append("")

    if include_score and report.issues:
        out.append("## Outstanding Issues")
        out.append("")
        out.append("| Severity | Section | Issue | Detail |")
        out.append("| --- | --- | --- | --- |")
        for issue in report.issues:
            out.append(
                f"| {issue.severity} | {_escape_cell(issue.section_title or issue.section_id)} "
                f"| {_escape_cell(issue.message)} | {_escape_cell(issue.detail)} |"
            )
        out.append("")

    return "\n".join(out).rstrip() + "\n"
