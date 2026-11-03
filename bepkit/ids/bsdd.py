"""bSDD: the dictionary URI behind the classification system a plan names.

An IDS classification facet may carry the URI of its system in the buildingSMART
Data Dictionary, so a checker resolves "Uniclass 2015" to one dictionary rather
than to whatever a free-text name suggests. The map in ``ids.bsdd_dictionaries``
answers offline; ``ids.bsdd_lookup`` asks the bSDD API for anything it lacks.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from ..settings import get as setting

_cache: dict[str, list[dict[str, Any]]] = {}


def _normal(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def dictionaries_offline() -> dict[str, str]:
    """System name -> dictionary URI, as configured."""
    return {str(k): str(v) for k, v in (setting("ids.bsdd_dictionaries", {}) or {}).items()}


def fetch_dictionaries(api: str | None = None, timeout: float | None = None) -> list[dict[str, Any]]:
    """Every dictionary bSDD lists, once per process."""
    api = api or str(setting("ids.bsdd_api", "https://api.bsdd.buildingsmart.org/api/Dictionary/v1"))
    if api not in _cache:
        with urllib.request.urlopen(api, timeout=timeout or float(setting("ids.bsdd_timeout", 5))) as response:
            data = json.load(response)
        _cache[api] = [
            {"name": d.get("name", ""), "version": str(d.get("version", "")),
             "uri": d.get("uri", ""), "latest": bool(d.get("isLatestVersion", False))}
            for d in data.get("dictionaries", [])
        ]
    return _cache[api]


def _match(system: str, names: dict[str, str]) -> str:
    """The exact name first, else the longest name the system text contains."""
    key = _normal(system)
    if not key:
        return ""
    by_name = {_normal(name): uri for name, uri in names.items() if _normal(name)}
    if key in by_name:
        return by_name[key]
    contained = [name for name in by_name if name in key]
    return by_name[max(contained, key=len)] if contained else ""


def classification_uri(system: str, *, lookup: bool | None = None) -> str:
    """The bSDD dictionary URI for ``system``, or an empty string when none is known."""
    uri = _match(system, dictionaries_offline())
    if uri or not system:
        return uri
    if lookup is None:
        lookup = bool(setting("ids.bsdd_lookup", False))
    if not lookup:
        return ""
    try:
        listed = fetch_dictionaries()
    except Exception:  # offline or slow: the facet simply carries no URI
        return ""
    names: dict[str, str] = {}
    for entry in listed:
        if entry["name"] and entry["uri"] and (entry["name"] not in names or entry["latest"]):
            names[entry["name"]] = entry["uri"]
    return _match(system, names)
