"""Render a project as a standalone, printable HTML document.

No external assets: the file can be emailed, archived in the CDE, or printed to
PDF from any browser without losing its formatting.
"""

from __future__ import annotations

import html as html_escape
from typing import Any

from ..models import Project
from ..schema.models import Field, Framework
from ..scoring import ScoreReport
from ..scoring.rules import table_rows

DOC_CSS = """
:root { --ink:#16181d; --muted:#61656e; --line:#e3e5ea; --accent:#1f5f8b; --bg:#fff; }
* { box-sizing:border-box; }
body { margin:0; background:#f4f5f7; color:var(--ink);
  font:15px/1.65 "Inter","Segoe UI",-apple-system,system-ui,sans-serif; }
.page { max-width:900px; margin:0 auto; padding:56px 64px; background:var(--bg); }
h1 { font-size:30px; margin:0 0 6px; letter-spacing:-0.02em; }
h2 { font-size:19px; margin:44px 0 10px; padding-bottom:7px; border-bottom:2px solid var(--accent);
  letter-spacing:-0.01em; }
h3 { font-size:14px; margin:22px 0 6px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
p, li { margin:0 0 10px; }
.lede { color:var(--muted); margin-bottom:26px; }
.meta { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px 22px;
  padding:18px 20px; background:#f8f9fb; border:1px solid var(--line); border-radius:8px; margin-bottom:28px; }
.meta div span { display:block; font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.meta div strong { font-weight:600; }
.scorecard { display:flex; gap:20px; align-items:center; padding:20px 24px; border:1px solid var(--line);
  border-radius:10px; margin-bottom:26px; background:#fbfcfd; }
.scorecard .big { font-size:44px; font-weight:700; line-height:1; letter-spacing:-0.03em; }
.scorecard .big small { font-size:16px; color:var(--muted); font-weight:500; }
.badge { display:inline-block; padding:3px 10px; border-radius:99px; font-size:11px; font-weight:600;
  letter-spacing:.05em; text-transform:uppercase; background:#e8eef4; color:var(--accent); }
table { width:100%; border-collapse:collapse; margin:8px 0 14px; font-size:13.5px; }
th, td { border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top; }
th { background:#f4f6f8; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
.empty { color:#9aa0a8; font-style:italic; }
.ref { font-size:12px; color:var(--muted); margin:0 0 12px; }
.intent { font-size:13.5px; color:var(--muted); font-style:italic; margin-bottom:14px; }
.sev-blocker { color:#b3261e; font-weight:600; }
.sev-major { color:#a35a00; font-weight:600; }
.sev-minor { color:#5b6270; }
.bar { height:6px; background:#eceef1; border-radius:99px; overflow:hidden; min-width:90px; }
.bar i { display:block; height:100%; background:var(--accent); }
.toc { columns:2; column-gap:36px; font-size:14px; }
footer { margin-top:48px; padding-top:16px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); }
@media print {
  body { background:#fff; } .page { padding:0; max-width:none; }
  h2 { page-break-after:avoid; } table, .scorecard { page-break-inside:avoid; }
}
"""


def esc(value: Any) -> str:
    return html_escape.escape(str(value or ""))


def _prose(text: str) -> str:
    paragraphs = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    return "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)


def render_field(field: Field, value: Any) -> str:
    if value is None or value == "" or value == []:
        return '<p class="empty">Not yet completed.</p>'

    if field.type == "table":
        rows = table_rows(value)
        if not rows:
            return '<p class="empty">Not yet completed.</p>'
        head = "".join(f"<th>{esc(c.label)}</th>" for c in field.columns)
        body = "".join(
            "<tr>" + "".join(f"<td>{esc(row.get(c.id)) or '—'}</td>" for c in field.columns) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    if field.type in ("multiselect", "list"):
        items = value if isinstance(value, list) else [value]
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items if str(i).strip()) + "</ul>"

    if field.type == "boolean":
        return "<p>Yes</p>" if value else "<p>No</p>"

    return _prose(value)


def render(project: Project, framework: Framework, report: ScoreReport, *, include_score: bool = True) -> str:
    values = project.values()
    parts: list[str] = []
    parts.append(f"<h1>BIM Execution Plan</h1>")
    parts.append(f'<p class="lede">{esc(project.name)}</p>')

    meta = [("Framework", f"{framework.name} v{framework.version}"), ("Status", project.status)]
    if project.client:
        meta.append(("Appointing party", project.client))
    if project.reference:
        meta.append(("Project reference", project.reference))
    if project.owner:
        meta.append(("Information manager", project.owner))
    meta.append(("Generated", report.generated_at.replace("T", " ").replace("+00:00", " UTC")))
    parts.append('<div class="meta">' + "".join(
        f"<div><span>{esc(k)}</span><strong>{esc(v)}</strong></div>" for k, v in meta
    ) + "</div>")

    if include_score:
        counts = report.issue_counts()
        parts.append(
            '<div class="scorecard">'
            f'<div class="big">{report.score:.0f}<small>/100</small></div>'
            "<div>"
            f'<span class="badge">{esc(report.maturity_label)}</span>'
            f"<p style=\"margin:8px 0 0\">{esc(report.maturity_note)}</p>"
            f'<p style="margin:4px 0 0;font-size:13px;color:#61656e">'
            f"Coverage {report.coverage:.0f}% · Required answered {report.required_coverage:.0f}% · "
            f"{counts['blocker']} blocking, {counts['major']} major issues · "
            f"{'Ready to issue' if report.is_ready else 'Not ready to issue'}</p>"
            "</div></div>"
        )
        parts.append("<h2>Section Completeness</h2>")
        rows = "".join(
            f"<tr><td>{esc(s.title)}</td><td style='width:120px'>"
            f"<div class='bar'><i style='width:{s.score:.0f}%'></i></div></td>"
            f"<td style='width:70px;text-align:right'>{s.score:.0f}</td>"
            f"<td style='width:90px;text-align:right'>{s.coverage:.0f}%</td></tr>"
            for s in report.sections
        )
        parts.append(
            "<table><thead><tr><th>Section</th><th></th><th style='text-align:right'>Score</th>"
            f"<th style='text-align:right'>Coverage</th></tr></thead><tbody>{rows}</tbody></table>"
        )

    parts.append("<h2>Contents</h2><ol class='toc'>")
    parts.extend(f"<li>{esc(s.title)}</li>" for s in framework.sections)
    parts.append("</ol>")

    for index, section in enumerate(framework.sections, start=1):
        parts.append(f"<h2>{index}. {esc(section.title)}</h2>")
        if section.reference:
            parts.append(f'<p class="ref">Reference: {esc(section.reference)}</p>')
        if section.intent:
            parts.append(f'<p class="intent">{esc(section.intent)}</p>')
        section_values = values.get(section.id) or {}
        for field in section.fields:
            marker = " *" if field.required else ""
            parts.append(f"<h3>{esc(field.label)}{marker}</h3>")
            parts.append(render_field(field, section_values.get(field.id)))

    if include_score and report.issues:
        parts.append("<h2>Outstanding Issues</h2>")
        rows = "".join(
            f'<tr><td class="sev-{esc(i.severity)}">{esc(i.severity)}</td>'
            f"<td>{esc(i.section_title or i.section_id)}</td>"
            f"<td>{esc(i.message)}{(' <em>' + esc(i.detail) + '</em>') if i.detail else ''}</td></tr>"
            for i in report.issues
        )
        parts.append(
            "<table><thead><tr><th style='width:90px'>Severity</th><th style='width:220px'>Section</th>"
            f"<th>Issue</th></tr></thead><tbody>{rows}</tbody></table>"
        )

    parts.append(
        f"<footer>{esc(project.name)} · {esc(framework.name)} · "
        f"Fields completed {report.fields_filled}/{report.fields_total} · "
        "Fields marked * are required by the framework.</footer>"
    )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>BEP — {esc(project.name)}</title><style>{DOC_CSS}</style></head>"
        f"<body><div class='page'>{''.join(parts)}</div></body></html>"
    )
