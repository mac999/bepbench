"""IDS export and model checking: the one place the web app and the CLI call.

A plan relates to IDS documents and IFC models one-to-many. Its level of
information need table spans several milestones, and a Stage 3 model must not
be checked against Stage 4 requirements, so an export can be cut to one
milestone or split into one document per milestone. A plan also has a model per
discipline, so a check runs against every attached model (or the ones asked
for) and reports each separately, each against its own schema.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from ..ids import (
    BuildResult,
    IdsError,
    build,
    milestone_column,
    milestones,
    normalise_schema,
    resolve_versions,
    validate_against,
)
from ..models import Project, slugify
from ..settings import get as setting
from .models import list_models
from .projects import framework_for

_FILE_SCHEMA = re.compile(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", re.IGNORECASE)


def ids_milestones(project: Project) -> dict[str, Any]:
    """The milestones the plan's LOIN table names, the column that holds them,
    and the one an export or check uses when none is asked for."""
    framework = framework_for(project)
    return {
        "column": milestone_column(framework.id),
        "milestones": milestones(framework.id, project.values()),
        "default": str(setting("ids.milestone", "") or ""),
    }


def ids_filename(project: Project, milestone: str = "") -> str:
    """The file name an export is saved under, from ``ids.filename`` settings."""
    pattern = (setting("ids.split_filename", "{slug}-{milestone}.ids") if milestone
               else setting("ids.filename", "{slug}.ids"))
    return pattern.format(slug=slugify(project.name) or project.slug,
                          milestone=slugify(milestone) or milestone)


def export_ids(project: Project, *, ifc_version: Any = None, milestone: str | None = None,
               default_pset: str | None = None) -> BuildResult:
    """One IDS document: every milestone, or the one asked for."""
    return build(project, framework_for(project), project.values(),
                 ifc_version=ifc_version, milestone=milestone, default_pset=default_pset)


def export_ids_split(project: Project, *, ifc_version: Any = None,
                     default_pset: str | None = None) -> list[tuple[str, BuildResult]]:
    """One IDS document per milestone named in the LOIN table."""
    found = ids_milestones(project)["milestones"]
    if not found:
        raise IdsError(
            "the level of information need table names no milestones, so there is "
            "nothing to split by. Fill its stage column, or export without splitting."
        )
    out: list[tuple[str, BuildResult]] = []
    for milestone in found:
        try:
            out.append((milestone, export_ids(project, ifc_version=ifc_version,
                                              milestone=milestone, default_pset=default_pset)))
        except IdsError:
            continue  # every row of this milestone was skipped; others still export
    if not out:
        raise IdsError("no milestone produced a specification.")
    return out


def file_schema(path: str) -> str:
    """The schema an IFC file declares in its header, read without parsing the model."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            head = handle.read(8192)
    except OSError:
        return ""
    match = _FILE_SCHEMA.search(head)
    return match.group(1).upper() if match else ""


def _targets(project: Project, model_ids: Iterable[int] | None,
             model_path: str | None) -> list[dict[str, Any]]:
    if model_path:
        return [{"model_id": None, "filename": Path(model_path).name,
                 "schema": file_schema(model_path), "path": model_path}]
    models = list_models(project)
    wanted = [int(i) for i in (model_ids or []) if i not in (None, "")]
    if wanted:
        unknown = sorted(set(wanted) - {m.id for m in models})
        if unknown:
            raise IdsError(f"no attached model with id {', '.join(str(u) for u in unknown)}")
        models = [m for m in models if m.id in wanted]
    if not models:
        raise IdsError("attach an IFC model to this plan first")
    return [{"model_id": m.id, "filename": m.filename, "schema": m.schema or "",
             "path": m.source_path} for m in models]


def check_ids(project: Project, *, model_ids: Iterable[int] | None = None,
              model_path: str | None = None, ifc_version: Any = None,
              milestone: str | None = None, default_pset: str | None = None,
              from_model: bool | None = None) -> dict[str, Any]:
    """Check each model against the plan's requirements, each in its own schema.

    The target schema is, in order: what the caller asked for, the model's own
    schema when ``ids.ifc_version_from_model`` is on, then ``ids.ifc_version``.
    """
    if from_model is None:
        from_model = bool(setting("ids.ifc_version_from_model", True))
    explicit = resolve_versions(ifc_version) if ifc_version else None

    reports: list[dict[str, Any]] = []
    errors: list[str] = []
    for target in _targets(project, model_ids, model_path):
        schema = normalise_schema(target["schema"]) if target["schema"] else ""
        if explicit:
            versions = explicit
        elif from_model and schema:
            versions = [schema]
        else:
            versions = resolve_versions(None)

        entry: dict[str, Any] = {
            "model_id": target["model_id"],
            "model": target["filename"],
            "schema": schema,
            "ifc_version": versions,
            "warning": "",
        }
        if schema and schema not in versions:
            entry["warning"] = (f"the model is {schema} but the requirements target "
                                f"{', '.join(versions)}")
        try:
            result = export_ids(project, ifc_version=versions, milestone=milestone,
                                default_pset=default_pset)
            report = validate_against(result.xml, target["path"], result.identifiers)
        except IdsError as exc:
            errors.append(f"{target['filename']}: {exc}")
            entry.update({"error": str(exc), "specifications": 0, "passed": 0,
                          "failed": 0, "not_applicable": 0, "results": []})
            reports.append(entry)
            continue
        except Exception as exc:  # an unreadable IFC is the author's to fix, not a crash
            errors.append(f"{target['filename']}: {exc}")
            entry.update({"error": f"could not read the model: {exc}", "specifications": 0,
                          "passed": 0, "failed": 0, "not_applicable": 0, "results": []})
            reports.append(entry)
            continue
        entry.update(report)
        entry["build"] = result.to_dict()
        reports.append(entry)

    if all("error" in r for r in reports):
        raise IdsError(errors[0].split(": ", 1)[-1] if len(reports) == 1 else "; ".join(errors))

    checked = [r for r in reports if "error" not in r]
    return {
        "milestone": str(milestone if milestone is not None else setting("ids.milestone", "")),
        "models": reports,
        # Totals over every model checked, so a single number gates CI.
        "specifications": sum(r["specifications"] for r in checked),
        "passed": sum(r["passed"] for r in checked),
        "failed": sum(r["failed"] for r in checked) + (len(reports) - len(checked)),
        "not_applicable": sum(r["not_applicable"] for r in checked),
        "results": [dict(item, model=r["model"]) for r in checked for item in r["results"]],
        "model": reports[0]["model"],
    }
