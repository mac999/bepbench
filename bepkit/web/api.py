"""JSON API.

The browser client uses it for autosave and live scoring; it is also the
integration surface for CI checks or a CDE hook that wants a project's score.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from flask import Blueprint, jsonify, request

from .. import services
from ..exporters import is_binary, render as render_export, render_bytes
from ..schema import available_frameworks, get_framework

api_bp = Blueprint("api", __name__)


def _error(message: str, status: int = 400):
    return jsonify(error=message), status


@api_bp.errorhandler(services.ServiceError)
def _service_error(exc):  # pragma: no cover - wired through Flask
    return _error(str(exc))


class _BadBody(Exception):
    pass


@api_bp.errorhandler(_BadBody)
def _bad_body(exc):  # pragma: no cover - wired through Flask
    return _error(str(exc))


def _body() -> dict[str, Any]:
    """The request's JSON object; anything else is the caller's mistake, not a crash."""
    body = request.get_json(silent=True)
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise _BadBody("send a JSON object")
    return body


def _load(slug: str):
    return services.get_project(slug)


@api_bp.get("/frameworks")
def frameworks():
    return jsonify([
        {
            "id": f.id,
            "name": f.name,
            "version": f.version,
            "description": f.description.strip(),
            "reference": f.reference,
            "sections": len(f.sections),
            "fields": f.total_fields,
            "checks": len(f.checks),
        }
        for f in available_frameworks()
    ])


@api_bp.get("/frameworks/<framework_id>")
def framework_detail(framework_id: str):
    try:
        framework = get_framework(framework_id)
    except KeyError as exc:
        return _error(str(exc), 404)
    return jsonify({
        "id": framework.id,
        "name": framework.name,
        "version": framework.version,
        "description": framework.description.strip(),
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "weight": s.weight,
                "intent": s.intent,
                "reference": s.reference,
                "fields": [
                    {
                        "id": f.id, "label": f.label, "type": f.type,
                        "required": f.required, "weight": f.weight, "help": f.help,
                        "options": f.options,
                        "columns": [{"id": c.id, "label": c.label, "type": c.type,
                                     "required": c.required, "options": c.options}
                                    for c in f.columns],
                    }
                    for f in s.fields
                ],
            }
            for s in framework.sections
        ],
    })


@api_bp.get("/projects")
def list_projects():
    out = []
    for project in services.list_projects():
        report = services.score_project(project)
        data = project.to_dict()
        data["score"] = round(report.score, 1)
        data["maturity"] = report.maturity_label
        data["ready_to_issue"] = report.is_ready
        out.append(data)
    return jsonify(out)


@api_bp.post("/projects")
def create_project():
    body = _body()
    try:
        project = services.create_project(
            name=body.get("name", ""),
            framework_id=body.get("framework", ""),
            client=body.get("client", ""),
            reference=body.get("reference", ""),
            owner=body.get("owner", ""),
            slug=body.get("slug"),
        )
    except services.ServiceError as exc:
        return _error(str(exc))
    return jsonify(project.to_dict()), 201


@api_bp.get("/projects/<slug>")
def get_project(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    return jsonify(services.export_dict(project))


@api_bp.patch("/projects/<slug>")
def patch_project(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    services.update_project(project, **_body())
    return jsonify(project.to_dict())


@api_bp.delete("/projects/<slug>")
def delete_project(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    services.delete_project(project)
    return jsonify(deleted=slug)


@api_bp.put("/projects/<slug>/values")
def put_values(slug: str):
    """Apply a batch of ``{"section.field": value}`` updates and return fresh scores.

    The editor calls this on every field blur, so the response carries exactly
    what the score rail needs to repaint without a second round trip.
    """
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)

    body = _body()
    updates = body.get("values", body)
    if not isinstance(updates, dict) or not updates:
        return _error("send a JSON object of section.field -> value")

    try:
        count = services.set_values(project, updates, author=body.get("author", ""))
    except services.ServiceError as exc:
        return _error(str(exc))

    report = services.score_project(project)
    touched = {path.split(".", 1)[0] for path in updates if "." in path}
    return jsonify({
        "updated": count,
        "score": round(report.score, 1),
        "coverage": round(report.coverage, 1),
        "required_coverage": round(report.required_coverage, 1),
        "maturity": {"label": report.maturity_label, "note": report.maturity_note,
                     "level": report.maturity_level, "next": report.next_band},
        "ready_to_issue": report.is_ready,
        "issue_counts": report.issue_counts(),
        "sections": [s.to_dict() | {"fields": []} for s in report.sections],
        "section_detail": [s.to_dict() for s in report.sections if s.id in touched],
        "section_issues": [i.to_dict() for i in report.issues if i.section_id in touched],
        "recommendations": [r.to_dict() for r in report.recommendations],
    })


@api_bp.get("/projects/<slug>/score")
def score(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    return jsonify(services.score_project(project).to_dict())


@api_bp.get("/projects/<slug>/export")
def export(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    fmt = request.args.get("format", "md")
    framework = services.framework_for(project)
    report = services.score_project(project)
    include_score = request.args.get("score", "1") != "0"
    try:
        if is_binary(fmt):  # Word and the like travel as base64 inside the JSON
            data = render_bytes(fmt, project, framework, report, include_score=include_score)
            return jsonify(format=fmt, encoding="base64",
                           content=base64.b64encode(data).decode("ascii"))
        body = render_export(fmt, project, framework, report, include_score=include_score)
    except ValueError as exc:
        return _error(str(exc))
    except RuntimeError as exc:          # an optional exporter is not installed
        return _error(str(exc), 503)
    return jsonify(format=fmt, content=body)


@api_bp.get("/projects/<slug>/snapshots")
def list_snapshots(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    return jsonify([s.to_dict() for s in project.snapshots])


@api_bp.post("/projects/<slug>/snapshots")
def create_snapshot(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    body = _body()
    snapshot = services.take_snapshot(project, body.get("label", ""))
    return jsonify(snapshot.to_dict()), 201


@api_bp.post("/import")
def import_project():
    body = _body()
    try:
        project = services.import_dict(body)
    except services.ServiceError as exc:
        return _error(str(exc))
    return jsonify(project.to_dict()), 201


# ---------------------------------------------------------------------------
# AI assistance
# ---------------------------------------------------------------------------

@api_bp.get("/ai/status")
def ai_status():
    from ..ai import status

    return jsonify(status())


@api_bp.post("/projects/<slug>/assist")
def assist(slug: str):
    """Draft, improve, expand or critique one field with the configured model.

    The suggestion is returned, never stored: the author decides whether it goes
    into the plan. That boundary matters — a BEP is a contractual commitment.
    """
    from ..ai import AIError, suggest
    from ..i18n import get_locale
    from ..schema.locale import localize

    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)

    body = _body()
    path = body.get("path", "")
    if "." not in path:
        return _error("send a 'path' of the form section.field")
    section_id, field_id = path.split(".", 1)

    language = body.get("language") or get_locale()
    framework = localize(services.framework_for(project), language)
    section = framework.section_by_id(section_id)
    field = section.field_by_id(field_id) if section else None
    if field is None:
        return _error(f"unknown field '{path}'", 404)

    values = project.values()
    try:
        result = suggest(
            project, framework, section, field,
            mode=body.get("mode", "draft"),
            current_value=values.get(section_id, {}).get(field_id),
            language=language,
            values=values,
            instruction=body.get("instruction", ""),
            model=body.get("model"),
        )
    except AIError as exc:
        return _error(str(exc), 503)
    return jsonify(result)


# ---------------------------------------------------------------------------
# IFC models
# ---------------------------------------------------------------------------

@api_bp.get("/projects/<slug>/models")
def list_models(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    return jsonify([m.to_dict() for m in services.list_models(project)])


@api_bp.post("/projects/<slug>/models")
def upload_model(slug: str):
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _error("attach an .ifc file as 'file'")
    try:
        model = services.attach_model(
            project, upload.stream, upload.filename,
            discipline=request.form.get("discipline", ""),
        )
    except services.ServiceError as exc:
        return _error(str(exc))
    return jsonify(model.to_dict()), 201


@api_bp.delete("/projects/<slug>/models/<int:model_id>")
def delete_model(slug: str, model_id: int):
    try:
        project = _load(slug)
        model = services.get_model(project, model_id)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    services.delete_model(project, model)
    return jsonify(deleted=model_id)


@api_bp.get("/projects/<slug>/models/<int:model_id>/index")
def model_index(slug: str, model_id: int):
    from flask import send_file

    try:
        project = _load(slug)
        model = services.get_model(project, model_id)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    if model.status != "ready" or not os.path.isfile(model.index_path):
        return _error(model.error or "this model has no viewer data; upload it again", 404)
    return send_file(model.index_path, mimetype="application/json",
                     max_age=0, conditional=True, etag=True)


@api_bp.get("/projects/<slug>/models/<int:model_id>/buffer")
def model_buffer(slug: str, model_id: int):
    from flask import send_file

    try:
        project = _load(slug)
        model = services.get_model(project, model_id)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    if model.status != "ready" or not os.path.isfile(model.buffer_path):
        return _error(model.error or "this model has no viewer data; upload it again", 404)
    return send_file(model.buffer_path, mimetype="application/octet-stream",
                     max_age=0, conditional=True, etag=True)


@api_bp.get("/settings/viewer")
def viewer_settings():
    """Everything the viewer needs to configure itself, straight from the JSON."""
    from ..ifcio import ifcopenshell_available
    from ..settings import get as setting

    return jsonify({
        "enabled": bool(setting("viewer.enabled", True)) and ifcopenshell_available(),
        "server_supports_ifc": ifcopenshell_available(),
        "default_mode": setting("viewer.default_mode", "solid"),
        "modes": setting("viewer.modes", []),
        "transparency": setting("viewer.transparency", 0.3),
        "show_edges": setting("viewer.show_edges", True),
        "background_light": setting("viewer.background_light", "#eaeef2"),
        "background_dark": setting("viewer.background_dark", "#14171c"),
        "selection_colour": setting("viewer.selection_colour", "#ff8c1a"),
        "palette": setting("viewer.palette", {}),
        "lod": setting("viewer.lod", {}),
        "max_upload_mb": setting("viewer.max_upload_mb", 200),
        "ui": setting("ui", {}),
    })


@api_bp.get("/projects/<slug>/models/<int:model_id>/elements/<guid>")
def model_element(slug: str, model_id: int, guid: str):
    """Attributes and property sets for one element, read from the stored IFC."""
    from ..ifcio import IfcError, element_properties

    try:
        project = _load(slug)
        model = services.get_model(project, model_id)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    try:
        return jsonify(element_properties(model.source_path, guid))
    except IfcError as exc:
        return _error(str(exc), 404)


# ---------------------------------------------------------------------------
# IDS
# ---------------------------------------------------------------------------

def _ids_options(source: Any) -> dict[str, Any]:
    """The options the CLI's ids export and ids check take, under the same names."""
    getlist = getattr(source, "getlist", None)
    versions = getlist("ifc_version") if getlist else source.get("ifc_version")
    return {
        "ifc_version": versions or None,
        "milestone": source.get("milestone"),
        "default_pset": source.get("default_pset") or None,
    }


@api_bp.get("/projects/<slug>/ids/milestones")
def ids_milestones(slug: str):
    """The milestones the plan's level of information need table names."""
    from ..ids import IdsError

    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    try:
        return jsonify(services.ids_milestones(project))
    except IdsError as exc:
        return _error(str(exc), 422)


@api_bp.get("/projects/<slug>/ids")
def export_ids(slug: str):
    """The plan's information requirements as a buildingSMART IDS document."""
    from flask import Response

    from ..ids import IdsError

    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)
    options = _ids_options(request.args)
    try:
        result = services.export_ids(project, **options)
    except IdsError as exc:
        return _error(str(exc), 422)

    if request.args.get("report"):
        return jsonify(result.to_dict())
    filename = services.ids_filename(project, result.milestone)
    return Response(result.xml, mimetype="application/xml", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


@api_bp.post("/projects/<slug>/ids/check")
def check_ids(slug: str):
    """Validate attached models against the plan's own requirements."""
    from ..ids import IdsError

    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)

    body = _body()
    model_ids = body.get("model_ids") or ([body["model_id"]] if body.get("model_id") else None)
    try:
        report = services.check_ids(project, model_ids=model_ids, **_ids_options(body))
    except IdsError as exc:
        return _error(str(exc), 422)
    return jsonify(report)


@api_bp.get("/projects/<slug>/diff")
def diff(slug: str):
    """Field-level comparison between two versions of the plan."""
    try:
        project = _load(slug)
    except services.ServiceError as exc:
        return _error(str(exc), 404)

    snapshots = {s.id: s for s in project.snapshots}
    if not snapshots:
        return _error("this plan has no snapshots to compare against", 422)

    before = snapshots.get(request.args.get("before", type=int)) or list(snapshots.values())[-1]
    after = snapshots.get(request.args.get("after", type=int))
    report = (services.compare_snapshots(project, before, after) if after
              else services.compare_snapshot_to_current(project, before))
    return jsonify(report.to_dict())
