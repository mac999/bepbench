"""Discovery and caching of framework YAML definitions."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from .models import Framework

BUILTIN_DIR = Path(__file__).resolve().parent.parent / "frameworks"


def _search_dirs() -> list[Path]:
    dirs = [BUILTIN_DIR]
    extra = os.environ.get("BEP_FRAMEWORK_PATH", "")
    for part in extra.split(os.pathsep):
        if part.strip():
            dirs.append(Path(part.strip()).expanduser())
    return dirs


def load_framework_file(path: str | Path) -> Framework:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: framework file must contain a mapping")
    raw.setdefault("id", Path(path).stem)
    return Framework.from_dict(raw)


@lru_cache(maxsize=None)
def _registry() -> dict[str, Framework]:
    found: dict[str, Framework] = {}
    for directory in _search_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.y*ml")):
            fw = load_framework_file(path)
            found[fw.id] = fw  # later directories override builtins
    return found


def available_frameworks() -> list[Framework]:
    return sorted(_registry().values(), key=lambda f: f.name)


def get_framework(framework_id: str) -> Framework:
    try:
        return _registry()[framework_id]
    except KeyError as exc:
        known = ", ".join(sorted(_registry())) or "none"
        raise KeyError(f"unknown framework {framework_id!r} (available: {known})") from exc


def reload_frameworks() -> None:
    _registry.cache_clear()
