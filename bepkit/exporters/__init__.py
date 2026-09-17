"""Document exporters, selected by format name."""

from __future__ import annotations

import json
from typing import Any

from . import docx as docx_exporter
from . import html as html_exporter
from . import markdown as markdown_exporter

# name -> (mimetype, extension, binary?)
FORMATS: dict[str, tuple[str, str, bool]] = {
    "md": ("text/markdown; charset=utf-8", "md", False),
    "markdown": ("text/markdown; charset=utf-8", "md", False),
    "html": ("text/html; charset=utf-8", "html", False),
    "json": ("application/json; charset=utf-8", "json", False),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "docx", True),
}

ALIASES = {"word": "docx", "doc": "docx"}


def normalise(fmt: str) -> str:
    key = (fmt or "md").lower().strip()
    key = ALIASES.get(key, key)
    if key not in FORMATS:
        raise ValueError(
            f"unknown export format '{fmt}' (use: {', '.join(sorted(set(FORMATS) - set(ALIASES)))})"
        )
    return key


def render(fmt: str, project, framework, report, *, include_score: bool = True) -> str:
    """Text export. Raises for binary formats — use :func:`render_bytes`."""
    key = normalise(fmt)
    if FORMATS[key][2]:
        raise ValueError(f"'{key}' is a binary format; use render_bytes()")
    if key == "json":
        from ..services import export_dict

        return json.dumps(export_dict(project), indent=2, ensure_ascii=False)
    renderer = html_exporter.render if key == "html" else markdown_exporter.render
    return renderer(project, framework, report, include_score=include_score)


def render_bytes(fmt: str, project, framework, report, *, include_score: bool = True) -> bytes:
    """Every format, as the bytes that should hit the disk or the wire."""
    key = normalise(fmt)
    if key == "docx":
        return docx_exporter.build(project, framework, report, include_score=include_score)
    return render(key, project, framework, report, include_score=include_score).encode("utf-8")


def mimetype(fmt: str) -> str:
    return FORMATS[normalise(fmt)][0]


def extension(fmt: str) -> str:
    return FORMATS[normalise(fmt)][1]


def is_binary(fmt: str) -> bool:
    return FORMATS[normalise(fmt)][2]


def available() -> list[dict[str, Any]]:
    """Formats offered in the UI, with any that are unavailable flagged."""
    return [
        {"id": "docx", "label": "Word (.docx)",
         "available": docx_exporter.DOCX_AVAILABLE},
        {"id": "md", "label": "Markdown (.md)", "available": True},
        {"id": "html", "label": "Web page (.html)", "available": True},
        {"id": "json", "label": "Data (.json)", "available": True},
    ]


__all__ = ["render", "render_bytes", "mimetype", "extension", "is_binary",
           "normalise", "available", "FORMATS"]
