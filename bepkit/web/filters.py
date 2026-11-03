"""Jinja filters and globals shared by the templates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from markupsafe import Markup, escape

SEVERITY_LABELS = {
    "blocker": "Blocking",
    "major": "Major",
    "minor": "Minor",
    "info": "Info",
}


def score_tone(value: float) -> str:
    """Map a 0-100 score onto the palette's semantic tones."""
    if value >= 85:
        return "excellent"
    if value >= 65:
        return "good"
    if value >= 45:
        return "fair"
    if value > 0:
        return "weak"
    return "empty"


def relative_time(value: Any) -> str:
    if not isinstance(value, datetime):
        return ""
    now = datetime.now(timezone.utc)
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if seconds < 604800:
        return f"{int(seconds // 86400)} d ago"
    return moment.strftime("%d %b %Y")


def nl2br(value: Any) -> Markup:
    return Markup("<br>".join(escape(line) for line in str(value or "").splitlines()))


def severity_label(value: str) -> str:
    return SEVERITY_LABELS.get(value, value.title())


def columns_json(columns: Any) -> Markup:
    """Serialise table columns for the JavaScript row builder."""
    payload = [
        {"id": c.id, "label": c.label, "type": c.type,
         "required": c.required, "options": c.options, "width": c.width,
         "suggest": c.suggest}
        for c in columns
    ]
    # Embedded in a single-quoted HTML attribute, so only quotes need escaping.
    return Markup(json.dumps(payload, ensure_ascii=False).replace("'", "&#39;"))


FILTERS = {
    "score_tone": score_tone,
    "columns_json": columns_json,
    "relative_time": relative_time,
    "nl2br": nl2br,
    "severity_label": severity_label,
}

def _ifc_classes() -> list[str]:
    from ..ids import known_classes

    return [c["name"] for c in known_classes()]


# A column's `suggest:` names one of these; the editor offers it as a datalist.
SUGGESTIONS = {
    "ifc_classes": _ifc_classes,
}


def suggestions(name: str) -> list[str]:
    """Values a column offers, or none when the source is unavailable."""
    source = SUGGESTIONS.get(name)
    if source is None:
        return []
    try:
        return source()
    except Exception:
        return []


GLOBALS = {
    "now": lambda: datetime.now(timezone.utc),
    "suggestions": suggestions,
}
