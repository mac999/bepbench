"""Application services: everything the web and CLI front ends both need.

Neither front end talks to the ORM directly, so behaviour (validation, value
coercion, scoring, snapshots) cannot drift between them.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import select

from ..extensions import db
from ..models import Answer, Project, Snapshot, slugify, utcnow
from ..schema import Framework, get_framework
from ..schema.models import STAGES, Field
from ..scoring import ScoreReport, evaluate


class ServiceError(Exception):
    """Raised for conditions the caller is expected to report to a human."""


# --------------------------------------------------------------------------
# Value coercion
# --------------------------------------------------------------------------

TRUE_WORDS = {"1", "true", "yes", "y", "on"}
FALSE_WORDS = {"0", "false", "no", "n", "off", ""}


def coerce_value(field: Field, raw: Any) -> Any:
    """Turn a form post, a JSON body or a CLI string into the stored shape."""
    if raw is None:
        return None

    if field.type == "boolean":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in TRUE_WORDS

    if field.type == "number":
        if isinstance(raw, (int, float)):
            return raw
        text = str(raw).strip()
        if not text:
            return None
        try:
            return float(text) if "." in text else int(text)
        except ValueError as exc:
            raise ServiceError(f"{field.label}: '{raw}' is not a number") from exc

    if field.type in ("multiselect", "list"):
        if isinstance(raw, list):
            items = raw
        else:
            text = str(raw).strip()
            if text.startswith("["):
                try:
                    items = json.loads(text)
                except json.JSONDecodeError:
                    items = [p.strip() for p in text.split(",")]
            else:
                items = [p.strip() for p in text.split(",")]
        items = [str(i).strip() for i in items if str(i).strip()]
        if field.type == "multiselect" and field.options:
            allowed = {o.lower(): o for o in field.options}
            unknown = [i for i in items if i.lower() not in allowed]
            if unknown:
                raise ServiceError(f"{field.label}: unknown option(s) {', '.join(unknown)}")
            items = [allowed[i.lower()] for i in items]
        return items

    if field.type == "table":
        rows = raw
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return []
            try:
                rows = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ServiceError(f"{field.label}: table values must be JSON rows") from exc
        if not isinstance(rows, list):
            raise ServiceError(f"{field.label}: table values must be a list of rows")
        column_ids = [c.id for c in field.columns]
        cleaned: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ServiceError(f"{field.label}: each table row must be an object")
            cleaned_row = {cid: str(row.get(cid, "") or "").strip() for cid in column_ids}
            if any(cleaned_row.values()):
                cleaned.append(cleaned_row)
        return cleaned

    if field.type == "select":
        text = str(raw).strip()
        if not text:
            return ""
        if field.options:
            allowed = {o.lower(): o for o in field.options}
            if text.lower() not in allowed:
                raise ServiceError(
                    f"{field.label}: '{text}' is not one of: {', '.join(field.options)}"
                )
            return allowed[text.lower()]
        return text

    return str(raw)


# --------------------------------------------------------------------------
# Project lifecycle
# --------------------------------------------------------------------------

def list_projects() -> list[Project]:
    return list(db.session.scalars(select(Project).order_by(Project.updated_at.desc())))


def get_project(slug: str) -> Project:
    project = db.session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise ServiceError(f"no project with reference '{slug}'")
    return project


def unique_slug(base: str) -> str:
    slug = slugify(base)
    candidate, counter = slug, 2
    while db.session.scalar(select(Project).where(Project.slug == candidate)):
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def create_project(
    name: str,
    framework_id: str,
    *,
    client: str = "",
    reference: str = "",
    owner: str = "",
    slug: str | None = None,
    stage: str = "delivery",
) -> Project:
    if not (name or "").strip():
        raise ServiceError("project name is required")
    try:
        get_framework(framework_id)
    except KeyError as exc:
        raise ServiceError(str(exc)) from exc

    if stage not in STAGES:
        raise ServiceError(f"unknown stage '{stage}' (use: {', '.join(STAGES)})")

    project = Project(
        slug=unique_slug(slug or name),
        name=name.strip(),
        framework_id=framework_id,
        client=client.strip(),
        reference=reference.strip(),
        owner=owner.strip(),
        stage=stage,
    )
    db.session.add(project)
    db.session.commit()
    _seed_header_fields(project)
    return project


def _seed_header_fields(project: Project) -> None:
    """Pre-fill the obvious identity fields so the first screen is not blank."""
    framework = framework_for(project)
    seeds = {
        "project_name": project.name,
        "project_number": project.reference,
        "appointing_party": project.client,
        "client": project.client,
        "owner": project.client,
    }
    changed = False
    for section, field in framework.iter_fields():
        value = seeds.get(field.id)
        if value and field.type in ("text", "markdown"):
            set_value(project, section.id, field.id, value, commit=False)
            changed = True
    if changed:
        db.session.commit()


def update_project(project: Project, **attrs: Any) -> Project:
    if attrs.get("stage") and attrs["stage"] not in STAGES:
        raise ServiceError(f"unknown stage '{attrs['stage']}' (use: {', '.join(STAGES)})")
    for key in ("name", "client", "reference", "status", "owner", "notes", "stage"):
        if key in attrs and attrs[key] is not None:
            setattr(project, key, str(attrs[key]).strip())
    project.updated_at = utcnow()
    db.session.commit()
    return project


def delete_project(project: Project) -> None:
    db.session.delete(project)
    db.session.commit()


def framework_for(project: Project) -> Framework:
    try:
        return get_framework(project.framework_id)
    except KeyError as exc:
        raise ServiceError(
            f"project '{project.slug}' uses framework '{project.framework_id}', which is not installed"
        ) from exc


# --------------------------------------------------------------------------
# Answers
# --------------------------------------------------------------------------

def resolve_field(framework: Framework, section_id: str, field_id: str) -> Field:
    section = framework.section_by_id(section_id)
    if section is None:
        raise ServiceError(f"unknown section '{section_id}'")
    field = section.field_by_id(field_id)
    if field is None:
        raise ServiceError(f"unknown field '{section_id}.{field_id}'")
    return field


def set_value(
    project: Project,
    section_id: str,
    field_id: str,
    raw: Any,
    *,
    author: str = "",
    commit: bool = True,
) -> Any:
    framework = framework_for(project)
    field = resolve_field(framework, section_id, field_id)
    value = coerce_value(field, raw)

    answer = project.answer(section_id, field_id)
    if answer is None:
        answer = Answer(project=project, section_id=section_id, field_id=field_id)
        db.session.add(answer)
    answer.value = value
    answer.updated_by = author or answer.updated_by or ""
    answer.updated_at = utcnow()
    project.updated_at = utcnow()
    if commit:
        db.session.commit()
    return value


def set_values(project: Project, updates: dict[str, Any], *, author: str = "") -> int:
    """Apply a ``{"section.field": value}`` batch in one transaction."""
    count = 0
    for path, raw in updates.items():
        if "." not in path:
            raise ServiceError(f"'{path}' is not a section.field path")
        section_id, field_id = path.split(".", 1)
        set_value(project, section_id, field_id, raw, author=author, commit=False)
        count += 1
    db.session.commit()
    return count


def clear_value(project: Project, section_id: str, field_id: str) -> None:
    answer = project.answer(section_id, field_id)
    if answer is not None:
        db.session.delete(answer)
        project.updated_at = utcnow()
        db.session.commit()


# --------------------------------------------------------------------------
# Scoring and snapshots
# --------------------------------------------------------------------------

def score_project(project: Project, stage: str | None = None) -> ScoreReport:
    """Score the plan against the stage it is written for."""
    return evaluate(framework_for(project), project.values(),
                    stage=stage or project.stage or None)


def take_snapshot(project: Project, label: str = "") -> Snapshot:
    report = score_project(project)
    snapshot = Snapshot(
        project=project,
        label=label or f"Snapshot {utcnow():%Y-%m-%d %H:%M}",
        score=report.score,
        maturity_label=report.maturity_label,
    )
    snapshot.data = {"values": project.values(), "report": report.to_dict()}
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def restore_snapshot(project: Project, snapshot: Snapshot) -> int:
    values = snapshot.data.get("values") or {}
    for answer in list(project.answers):
        db.session.delete(answer)
    db.session.flush()
    # Drop the cached collection: it still holds the deleted rows, and set_value
    # would otherwise write to objects that are on their way out of the session.
    db.session.expire(project, ["answers"])
    count = 0
    for section_id, fields in values.items():
        for field_id, value in fields.items():
            try:
                set_value(project, section_id, field_id, value, commit=False)
                count += 1
            except ServiceError:
                continue  # framework changed since the snapshot; skip stale fields
    db.session.commit()
    return count


# --------------------------------------------------------------------------
# Portability
# --------------------------------------------------------------------------

def export_dict(project: Project) -> dict[str, Any]:
    report = score_project(project)
    return {
        "bep_format": 1,
        "project": project.to_dict(),
        "values": project.values(),
        "score": report.to_dict(),
    }


def import_dict(payload: dict[str, Any], *, slug: str | None = None) -> Project:
    meta = payload.get("project") or {}
    framework_id = meta.get("framework") or payload.get("framework")
    if not framework_id:
        raise ServiceError("import payload has no framework id")
    project = create_project(
        name=meta.get("name") or "Imported BEP",
        framework_id=framework_id,
        client=meta.get("client", ""),
        reference=meta.get("reference", ""),
        owner=meta.get("owner", ""),
        slug=slug or meta.get("slug"),
        stage=meta.get("stage") or "delivery",
    )
    skipped = 0
    for section_id, fields in (payload.get("values") or {}).items():
        for field_id, value in (fields or {}).items():
            try:
                set_value(project, section_id, field_id, value, commit=False)
            except ServiceError:
                skipped += 1
    db.session.commit()
    if skipped:
        project.notes = f"{project.notes}\nImport skipped {skipped} unrecognised field(s)."
        db.session.commit()
    return project


def bulk_progress(projects: Iterable[Project]) -> dict[str, ScoreReport]:
    return {p.slug: score_project(p) for p in projects}
