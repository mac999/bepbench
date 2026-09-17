"""Turning a field plus its project context into a drafting prompt.

The value here is not the model — it is the context. A generic chatbot writes
generic BEP prose; this builds a prompt that already knows the framework clause,
the depth the scoring engine will demand, the table columns that must be filled,
and what the rest of the plan already says, so the draft is consistent with the
document it is going into.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..schema.models import Field, Framework, Section
from ..scoring.rules import table_rows
from ..settings import get as setting
from .provider import AIError, Completion, get_provider

LANGUAGE_NAMES = {"en": "English", "ko": "Korean (한국어)"}

MODES = ("draft", "improve", "expand", "critique")


def _context_block(framework: Framework, values: dict[str, Any], skip: str) -> str:
    """A compact digest of what the plan already commits to."""
    limit = int(setting("ai.context_answers", 10))
    chars = int(setting("ai.context_chars_per_answer", 600))
    lines: list[str] = []
    for section in framework.sections:
        for field in section.fields:
            path = f"{section.id}.{field.id}"
            if path == skip:
                continue
            value = (values.get(section.id) or {}).get(field.id)
            if value in (None, "", []):
                continue
            if field.type == "table":
                rows = table_rows(value)
                if not rows:
                    continue
                summary = "; ".join(
                    " / ".join(str(cell) for cell in row.values() if str(cell).strip())[:120]
                    for row in rows[:4]
                )
                rendered = f"{len(rows)} rows — {summary}"
            elif isinstance(value, list):
                rendered = ", ".join(str(v) for v in value)
            else:
                rendered = " ".join(str(value).split())
            lines.append(f"- {section.title} / {field.label}: {rendered[:chars]}")
            if len(lines) >= limit:
                return "\n".join(lines)
    return "\n".join(lines)


def _expectations(field: Field) -> str:
    wants: list[str] = []
    q = field.quality
    if q.min_words:
        wants.append(f"at least {q.min_words} words of substantive content")
    if q.min_rows:
        wants.append(f"at least {q.min_rows} rows")
    if q.min_items:
        wants.append(f"at least {q.min_items} entries")
    if field.required:
        wants.append("this field is mandatory under the framework")
    return "; ".join(wants)


def build_prompt(
    project: Any,
    framework: Framework,
    section: Section,
    field: Field,
    *,
    mode: str = "draft",
    current_value: Any = None,
    language: str = "en",
    values: dict[str, Any] | None = None,
    instruction: str = "",
) -> str:
    language_name = LANGUAGE_NAMES.get(language, "English")
    parts: list[str] = []

    parts.append("# Project")
    parts.append(f"Name: {project.name}")
    if project.client:
        parts.append(f"Appointing party: {project.client}")
    if project.reference:
        parts.append(f"Project reference: {project.reference}")
    parts.append(f"Framework: {framework.name}")

    context = _context_block(framework, values or {}, f"{section.id}.{field.id}")
    if context:
        parts.append("\n# What the plan already says\n"
                     "Stay consistent with these commitments; do not contradict them.\n" + context)

    parts.append(f"\n# The field to write\nSection: {section.title}")
    if section.reference:
        parts.append(f"Framework clause: {section.reference}")
    if section.intent:
        parts.append(f"Purpose of the section: {section.intent}")
    parts.append(f"Field: {field.label}")
    if field.help:
        parts.append(f"Field guidance: {field.help}")
    if field.reference:
        parts.append(f"Field reference: {field.reference}")
    expectations = _expectations(field)
    if expectations:
        parts.append(f"Assessed against: {expectations}")

    if field.type == "table":
        columns = ", ".join(f'"{c.id}" ({c.label}{", required" if c.required else ""})'
                            for c in field.columns)
        option_notes = [f'"{c.id}" must be one of {c.options}' for c in field.columns if c.options]
        parts.append(
            "\n# Output format\n"
            f"Return ONLY a JSON array of objects. Every object must use exactly these keys: {columns}. "
            "Every value must be a string. No markdown, no code fence, no commentary."
        )
        if option_notes:
            parts.append("Constraints: " + "; ".join(option_notes) + ". Use those values verbatim.")
    elif field.type == "select":
        parts.append(f"\n# Output format\nReturn exactly one of these values and nothing else: {field.options}")
    elif field.type in ("markdown", "textarea"):
        parts.append("\n# Output format\nReturn plain prose paragraphs. No headings, no bullet list "
                     "unless the content is genuinely a list, no preamble.")
    else:
        parts.append("\n# Output format\nReturn a single short value with no punctuation around it.")

    if current_value not in (None, "", []):
        rendered = json.dumps(current_value, ensure_ascii=False, indent=1) \
            if isinstance(current_value, list) else str(current_value)
        parts.append(f"\n# The author's current text\n{rendered[:4000]}")

    parts.append("\n# Task\n" + setting(f"ai.modes.{mode}", setting("ai.modes.draft", "Draft this field.")))
    if instruction.strip():
        parts.append("Additional instruction from the author, which takes priority: " + instruction.strip())
    if field.type == "table" and mode == "critique":
        parts.append("Return the critique as plain bullets, not JSON.")
    parts.append(f"Write in {language_name}. Keep proper nouns, standard numbers "
                 "(ISO 19650, IFC 4, Uniclass) and file naming codes in their original form.")

    return "\n".join(parts)


JSON_ARRAY = re.compile(r"\[\s*\{.*\}\s*\]", re.DOTALL)


def parse_rows(text: str, field: Field) -> list[dict[str, str]] | None:
    """Pull table rows out of a model answer, tolerating the usual sloppiness."""
    match = JSON_ARRAY.search(text)
    if not match:
        return None
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list):
        return None

    column_ids = [c.id for c in field.columns]
    by_label = {c.label.lower(): c.id for c in field.columns}
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = {cid: "" for cid in column_ids}
        for key, value in item.items():
            target = key if key in row else by_label.get(str(key).lower())
            if target:
                row[target] = "" if value is None else str(value).strip()
        if any(row.values()):
            rows.append(row)
    return rows or None


def suggest(
    project: Any,
    framework: Framework,
    section: Section,
    field: Field,
    *,
    mode: str = "draft",
    current_value: Any = None,
    language: str = "en",
    values: dict[str, Any] | None = None,
    instruction: str = "",
    model: str | None = None,
) -> dict[str, Any]:
    """Ask the configured model for a draft of one field."""
    if not setting("ai.enabled", True):
        raise AIError("AI assistance is disabled in the settings file")
    if mode not in MODES:
        raise AIError(f"unknown mode '{mode}' (use: {', '.join(MODES)})")

    prompt = build_prompt(project, framework, section, field, mode=mode,
                          current_value=current_value, language=language,
                          values=values, instruction=instruction)
    completion: Completion = get_provider().complete(
        setting("ai.system_prompt", ""), prompt, model=model,
    )

    result: dict[str, Any] = {
        "path": f"{section.id}.{field.id}",
        "mode": mode,
        "text": completion.text,
        "model": completion.model,
        "provider": completion.provider,
        "elapsed_ms": completion.elapsed_ms,
        "applicable": mode != "critique",
    }
    if field.type == "table" and mode != "critique":
        rows = parse_rows(completion.text, field)
        if rows is None:
            result["applicable"] = False
            result["warning"] = "The model did not return valid table rows; showing its raw answer."
        else:
            result["rows"] = rows
            result["text"] = json.dumps(rows, ensure_ascii=False, indent=1)
    return result
