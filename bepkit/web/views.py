"""Server-rendered screens."""

from __future__ import annotations

import json

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .. import services
from ..exporters import extension, mimetype, render as render_export, render_bytes
from ..i18n import COOKIE_NAME, normalise_locale, get_locale
from ..models import slugify
from ..schema import available_frameworks, get_framework
from ..schema.locale import localize
from ..settings import get as setting

web_bp = Blueprint("web", __name__)


def _project_or_404(slug: str):
    try:
        return services.get_project(slug)
    except services.ServiceError:
        abort(404)


def _framework(project):
    """The project's framework, with labels in the reader's language."""
    return localize(services.framework_for(project), get_locale())


def _frameworks():
    return [localize(f, get_locale()) for f in available_frameworks()]


@web_bp.get("/lang/<code>")
def set_language(code: str):
    """Switch interface language and return the reader to where they were."""
    target = request.args.get("next") or request.referrer or url_for("web.dashboard")
    response = redirect(target)
    response.set_cookie(
        COOKIE_NAME, normalise_locale(code),
        max_age=60 * 60 * 24 * 365, samesite="Lax", httponly=False,
    )
    return response


@web_bp.get("/")
def dashboard():
    projects = services.list_projects()
    reports = {p.slug: services.score_project(p) for p in projects}
    portfolio = (
        sum(r.score for r in reports.values()) / len(reports) if reports else 0.0
    )
    blockers = sum(len(r.blockers) for r in reports.values())
    ready = sum(1 for r in reports.values() if r.is_ready)
    return render_template(
        "dashboard.html",
        projects=projects,
        reports=reports,
        frameworks=_frameworks(),
        portfolio_score=portfolio,
        total_blockers=blockers,
        ready_count=ready,
    )


@web_bp.post("/projects")
def create_project():
    form = request.form
    try:
        project = services.create_project(
            name=form.get("name", ""),
            framework_id=form.get("framework", ""),
            client=form.get("client", ""),
            reference=form.get("reference", ""),
            owner=form.get("owner", ""),
            stage=form.get("stage", "delivery"),
        )
    except services.ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("web.dashboard"))
    flash(f"Created “{project.name}”. Start with Project Information.", "success")
    return redirect(url_for("web.project_home", slug=project.slug))


@web_bp.get("/p/<slug>")
def project_home(slug: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    return redirect(url_for("web.editor", slug=project.slug, section_id=framework.sections[0].id))


@web_bp.get("/p/<slug>/s/<section_id>")
def editor(slug: str, section_id: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    section = framework.section_by_id(section_id)
    if section is None:
        abort(404)
    report = services.score_project(project)
    values = project.values().get(section.id, {})
    index = [s.id for s in framework.sections].index(section.id)

    # Which field, if any, drives the viewer's level of development on this page.
    lod_map = setting("viewer.lod.sections", {}) or {}
    lod_spec = lod_map.get(project.framework_id) or {}
    lod_field = (f"{lod_spec['section']}.{lod_spec['field']}"
                 if lod_spec.get("section") == section.id and lod_spec.get("field") else "")

    return render_template(
        "editor.html",
        project=project,
        framework=framework,
        section=section,
        section_number=index + 1,
        prev_section=framework.sections[index - 1] if index > 0 else None,
        next_section=framework.sections[index + 1] if index + 1 < len(framework.sections) else None,
        values=values,
        report=report,
        section_score=report.section(section.id),
        section_issues=[i for i in report.issues if i.section_id == section.id],
        lod_field=lod_field,
        lod_spec=lod_spec,
        models=services.list_models(project),
    )


@web_bp.post("/p/<slug>/s/<section_id>")
def save_section(slug: str, section_id: str):
    """Non-JavaScript fallback: a full form post for one section."""
    project = _project_or_404(slug)
    framework = _framework(project)
    section = framework.section_by_id(section_id)
    if section is None:
        abort(404)

    updates: dict[str, object] = {}
    for field in section.fields:
        key = f"f_{field.id}"
        if field.type == "table":
            raw = request.form.get(key, "")
            updates[f"{section.id}.{field.id}"] = raw or "[]"
        elif field.type == "multiselect":
            updates[f"{section.id}.{field.id}"] = request.form.getlist(key)
        elif field.type == "boolean":
            updates[f"{section.id}.{field.id}"] = key in request.form
        elif key in request.form:
            updates[f"{section.id}.{field.id}"] = request.form.get(key, "")

    try:
        services.set_values(project, updates, author=request.form.get("author", ""))
        flash(f"Saved {section.title}.", "success")
    except services.ServiceError as exc:
        flash(str(exc), "error")

    target = request.form.get("next") or section.id
    return redirect(url_for("web.editor", slug=project.slug, section_id=target))


@web_bp.get("/p/<slug>/score")
def score(slug: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    report = services.score_project(project)
    return render_template(
        "score.html", project=project, framework=framework, report=report,
        snapshots=project.snapshots,
    )


@web_bp.get("/p/<slug>/diff")
def diff(slug: str):
    """Compare two versions of the plan and show where the score moved."""
    project = _project_or_404(slug)
    snapshots = list(project.snapshots)
    if not snapshots:
        flash("Take a snapshot first — a diff needs something to compare against.", "error")
        return redirect(url_for("web.score", slug=project.slug))

    by_id = {s.id: s for s in snapshots}
    before = by_id.get(request.args.get("before", type=int)) or snapshots[-1]
    after = by_id.get(request.args.get("after", type=int))

    report = (services.compare_snapshots(project, before, after) if after
              else services.compare_snapshot_to_current(project, before))
    return render_template(
        "diff.html", project=project, framework=_framework(project),
        report=report, snapshots=snapshots,
        before_id=before.id, after_id=after.id if after else None,
    )


@web_bp.get("/p/<slug>/preview")
def preview(slug: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    report = services.score_project(project)
    return render_template(
        "preview.html", project=project, framework=framework, report=report,
        values=project.values(),
    )


@web_bp.get("/p/<slug>/document")
def document(slug: str):
    """The standalone printable document, rendered in its own window."""
    project = _project_or_404(slug)
    framework = _framework(project)
    report = services.score_project(project)
    include_score = request.args.get("score", "1") != "0"
    return Response(
        render_export("html", project, framework, report, include_score=include_score),
        mimetype="text/html",
    )


@web_bp.get("/p/<slug>/export")
def export(slug: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    report = services.score_project(project)
    fmt = request.args.get("format", "md")
    include_score = request.args.get("score", "1") != "0"
    try:
        body = render_bytes(fmt, project, framework, report, include_score=include_score)
    except ValueError as exc:
        abort(400, str(exc))
    except RuntimeError as exc:          # an optional exporter is not installed
        abort(503, str(exc))
    filename = f"BEP-{slugify(project.name)}.{extension(fmt)}"
    return Response(
        body,
        mimetype=mimetype(fmt),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@web_bp.get("/p/<slug>/settings")
def settings(slug: str):
    project = _project_or_404(slug)
    framework = _framework(project)
    return render_template(
        "settings.html", project=project, framework=framework,
        snapshots=project.snapshots, report=services.score_project(project),
    )


@web_bp.post("/p/<slug>/settings")
def update_settings(slug: str):
    project = _project_or_404(slug)
    services.update_project(
        project,
        name=request.form.get("name"),
        client=request.form.get("client"),
        reference=request.form.get("reference"),
        owner=request.form.get("owner"),
        status=request.form.get("status"),
        stage=request.form.get("stage"),
        notes=request.form.get("notes"),
    )
    flash("Project details updated.", "success")
    return redirect(url_for("web.settings", slug=project.slug))


@web_bp.post("/p/<slug>/snapshots")
def create_snapshot(slug: str):
    project = _project_or_404(slug)
    snapshot = services.take_snapshot(project, request.form.get("label", ""))
    flash(f"Snapshot saved at {snapshot.score:.0f}/100.", "success")
    return redirect(request.referrer or url_for("web.score", slug=project.slug))


@web_bp.post("/p/<slug>/snapshots/<int:snapshot_id>/restore")
def restore_snapshot(slug: str, snapshot_id: int):
    project = _project_or_404(slug)
    snapshot = next((s for s in project.snapshots if s.id == snapshot_id), None)
    if snapshot is None:
        abort(404)
    restored = services.restore_snapshot(project, snapshot)
    flash(f"Restored {restored} answers from “{snapshot.label}”.", "success")
    return redirect(url_for("web.score", slug=project.slug))


@web_bp.post("/p/<slug>/delete")
def delete_project(slug: str):
    project = _project_or_404(slug)
    if request.form.get("confirm") != project.slug:
        flash("Type the project reference exactly to confirm deletion.", "error")
        return redirect(url_for("web.settings", slug=project.slug))
    name = project.name
    services.delete_project(project)
    flash(f"Deleted “{name}”.", "success")
    return redirect(url_for("web.dashboard"))


@web_bp.post("/p/<slug>/duplicate")
def duplicate_project(slug: str):
    project = _project_or_404(slug)
    payload = services.export_dict(project)
    payload["project"]["name"] = f"{project.name} (copy)"
    payload["project"]["slug"] = None
    copy = services.import_dict(payload)
    flash(f"Duplicated as “{copy.name}”.", "success")
    return redirect(url_for("web.project_home", slug=copy.slug))


@web_bp.post("/import")
def import_project():
    upload = request.files.get("file")
    if not upload:
        flash("Choose a .json export to import.", "error")
        return redirect(url_for("web.dashboard"))
    try:
        payload = json.loads(upload.read().decode("utf-8"))
        project = services.import_dict(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        flash("That file is not valid BEP JSON.", "error")
        return redirect(url_for("web.dashboard"))
    except services.ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("web.dashboard"))
    flash(f"Imported “{project.name}”.", "success")
    return redirect(url_for("web.project_home", slug=project.slug))


@web_bp.get("/frameworks")
def frameworks():
    return render_template("frameworks.html", frameworks=_frameworks())


@web_bp.get("/frameworks/<framework_id>")
def framework_detail(framework_id: str):
    try:
        framework = localize(get_framework(framework_id), get_locale())
    except KeyError:
        abort(404)
    return render_template("framework_detail.html", framework=framework)
