"""Translation overlays for framework content.

A framework YAML is authored once in English. A sibling overlay in
``frameworks/locales/<framework_id>.<lang>.yaml`` supplies translated display
strings keyed by the same ids. Ids, option values and check rules are never
translated — they are data, and a plan must mean the same thing in both
languages.

Anything the overlay does not cover falls back to the English original, so a
partial translation is a valid translation.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import Check, Column, Field, Framework, Section

LOCALE_DIR = Path(__file__).resolve().parent.parent / "frameworks" / "locales"


def _overlay_path(framework_id: str, lang: str) -> Path:
    return LOCALE_DIR / f"{framework_id}.{lang}.yaml"


@lru_cache(maxsize=None)
def _overlay(framework_id: str, lang: str) -> dict[str, Any]:
    path = _overlay_path(framework_id, lang)
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _pick(source: dict[str, Any], key: str, fallback: str) -> str:
    value = source.get(key)
    return str(value) if value not in (None, "") else fallback


def _localize_field(field: Field, data: dict[str, Any]) -> Field:
    column_overlay = data.get("columns") or {}
    columns = [
        replace(column, label=_pick(column_overlay.get(column.id, {}) or {}, "label", column.label),
                help=_pick(column_overlay.get(column.id, {}) or {}, "help", column.help))
        if isinstance(column_overlay.get(column.id), dict)
        else replace(column, label=str(column_overlay.get(column.id) or column.label))
        for column in field.columns
    ]
    return replace(
        field,
        label=_pick(data, "label", field.label),
        help=_pick(data, "help", field.help),
        placeholder=_pick(data, "placeholder", field.placeholder),
        example=_pick(data, "example", field.example),
        columns=columns,
    )


def _localize_section(section: Section, data: dict[str, Any]) -> Section:
    field_overlay = data.get("fields") or {}
    return replace(
        section,
        title=_pick(data, "title", section.title),
        intent=_pick(data, "intent", section.intent),
        guidance=_pick(data, "guidance", section.guidance),
        fields=[_localize_field(f, field_overlay.get(f.id) or {}) for f in section.fields],
    )


@lru_cache(maxsize=None)
def _localized(framework_id: str, lang: str) -> Framework:
    # Keyed by id, not by the Framework itself: the dataclass holds lists and so
    # is not hashable, and the loader already caches the canonical instance.
    from .loader import get_framework

    framework = get_framework(framework_id)
    overlay = _overlay(framework_id, lang)
    if not overlay:
        return framework

    section_overlay = overlay.get("sections") or {}
    check_overlay = overlay.get("checks") or {}
    band_overlay = overlay.get("maturity_bands") or []

    bands = []
    for index, band in enumerate(framework.maturity_bands):
        translated = band_overlay[index] if index < len(band_overlay) else {}
        bands.append({
            **band,
            "label": _pick(translated, "label", band.get("label", "")),
            "note": _pick(translated, "note", band.get("note", "")),
        })

    return replace(
        framework,
        name=_pick(overlay, "name", framework.name),
        description=_pick(overlay, "description", framework.description),
        maturity_bands=bands,
        sections=[_localize_section(s, section_overlay.get(s.id) or {}) for s in framework.sections],
        checks=[
            replace(
                c,
                message=_pick(check_overlay.get(c.id) or {}, "message", c.message),
                fix=_pick(check_overlay.get(c.id) or {}, "fix", c.fix),
            )
            for c in framework.checks
        ],
    )


def localize(framework: Framework, lang: str | None) -> Framework:
    """Return ``framework`` with display strings in ``lang`` where available."""
    if not lang or lang == "en":
        return framework
    return _localized(framework.id, lang)


def available_locales(framework_id: str) -> list[str]:
    return sorted(p.name.split(".")[-2] for p in LOCALE_DIR.glob(f"{framework_id}.*.yaml"))


def clear_cache() -> None:
    _overlay.cache_clear()
    _localized.cache_clear()
