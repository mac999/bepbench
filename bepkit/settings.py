"""User-configurable settings, loaded from JSON.

Anything a BIM manager might reasonably want to change without touching Python
lives in ``bepkit/config_files/defaults.json``. A site override is deep-merged
over it, resolved in this order:

1. ``$BEP_CONFIG`` — an explicit path (file or directory of ``*.json``)
2. ``./bep.config.json`` in the working directory
3. ``<data dir>/config.json`` — the deployed instance's own settings
"""

from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULTS_PATH = Path(__file__).resolve().parent / "config_files" / "defaults.json"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Overlay wins for scalars and lists; dictionaries merge key by key."""
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        # A broken override must never take the app down; it is reported and skipped.
        print(f"bep: ignoring settings file {path}: {exc}")
        return {}


def override_paths() -> list[Path]:
    paths: list[Path] = []
    configured = os.environ.get("BEP_CONFIG")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("*.json")))
        elif candidate.is_file():
            paths.append(candidate)
    local = Path.cwd() / "bep.config.json"
    if local.is_file():
        paths.append(local)
    try:
        from .config import _data_dir

        instance = _data_dir() / "config.json"
        if instance.is_file():
            paths.append(instance)
    except Exception:  # pragma: no cover - data dir not writable
        pass
    return paths


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    merged = _read(DEFAULTS_PATH)
    for path in override_paths():
        merged = _deep_merge(merged, _read(path))
    return merged


def get(path: str, default: Any = None) -> Any:
    """Read a dotted settings path, e.g. ``get("ai.model")``."""
    node: Any = settings()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return copy.deepcopy(node) if isinstance(node, (dict, list)) else node


def reload() -> None:
    settings.cache_clear()
