"""Command line interface.

Every command runs against the same services as the web app, so a plan can be
started in the browser, scored in CI and exported from a Makefile without the
three disagreeing about what "complete" means.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click

from ..app import create_app
from ..i18n import LOCALES
from ..models import Project, slugify
from ..schema import available_frameworks, get_framework
from ..schema.locale import localize
from ..services import ServiceError
from .. import services

# ---------------------------------------------------------------------------
# presentation helpers
# ---------------------------------------------------------------------------

BLOCKS = "▏▎▍▌▋▊▉█"


def tone_colour(score: float) -> str:
    if score >= 85:
        return "green"
    if score >= 65:
        return "cyan"
    if score >= 45:
        return "yellow"
    if score > 0:
        return "red"
    return "white"


SEVERITY_COLOUR = {"blocker": "red", "major": "yellow", "minor": "cyan", "info": "white"}


def meter(value: float, width: int = 24) -> str:
    """A unicode progress meter that degrades to ASCII where needed."""
    filled = max(0.0, min(100.0, value)) / 100.0 * width
    whole = int(filled)
    remainder = filled - whole
    bar = "█" * whole
    if whole < width and remainder > 0.125:
        bar += BLOCKS[min(len(BLOCKS) - 1, int(remainder * len(BLOCKS)))]
    return click.style(bar.ljust(width, "·"), fg=tone_colour(value))


def echo_header(text: str) -> None:
    click.echo()
    click.secho(text, bold=True)
    click.secho("─" * min(len(text) + 2, 72), dim=True)


def fail(message: str) -> None:
    click.secho(f"error: {message}", fg="red", err=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# click plumbing
# ---------------------------------------------------------------------------

class Context:
    def __init__(self, lang: str) -> None:
        self.app = create_app()
        self.lang = lang
        self._ctx = self.app.app_context()
        self._ctx.push()

    def framework(self, project: Project):
        return localize(services.framework_for(project), self.lang)


pass_ctx = click.make_pass_decorator(Context)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--lang", default=lambda: os.environ.get("BEP_LANG", "en"),
              type=click.Choice(sorted(LOCALES)), show_default="en",
              help="Language for framework labels in the output.")
@click.version_option(package_name="bepbench", prog_name="bep", message="%(prog)s %(version)s")
@click.pass_context
def cli(ctx: click.Context, lang: str) -> None:
    """BEP Bench — author, score and export BIM Execution Plans."""
    ctx.obj = Context(lang)


# ---------------------------------------------------------------------------
# frameworks
# ---------------------------------------------------------------------------

@cli.command("frameworks")
@pass_ctx
def list_frameworks(ctx: Context) -> None:
    """List the installed frameworks."""
    echo_header("Frameworks")
    for framework in available_frameworks():
        localised = localize(framework, ctx.lang)
        click.echo(
            f"  {click.style(framework.id.ljust(12), fg='cyan')} {localised.name}  "
            + click.style(
                f"({len(framework.sections)} sections, {framework.total_fields} fields, "
                f"{len(framework.checks)} checks)", dim=True)
        )
    click.echo()


@cli.command("framework")
@click.argument("framework_id")
@pass_ctx
def show_framework(ctx: Context, framework_id: str) -> None:
    """Print the structure of one framework."""
    try:
        framework = localize(get_framework(framework_id), ctx.lang)
    except KeyError as exc:
        fail(str(exc))
    echo_header(f"{framework.name}  v{framework.version}")
    for index, section in enumerate(framework.sections, start=1):
        click.echo(f"\n{click.style(f'{index:02d} {section.title}', bold=True)} "
                   + click.style(f"weight {section.weight}", dim=True))
        for field in section.fields:
            marks = []
            if field.required:
                marks.append(click.style("required", fg="yellow"))
            if field.quality.min_words:
                marks.append(f"{field.quality.min_words}w")
            if field.quality.min_rows:
                marks.append(f"{field.quality.min_rows} rows")
            suffix = ("  " + click.style(" · ".join(marks), dim=True)) if marks else ""
            click.echo(f"   {section.id}.{field.id}".ljust(46)
                       + click.style(field.type.ljust(11), fg="cyan") + field.label + suffix)
    click.echo()


# ---------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------

@cli.command("new")
@click.argument("name")
@click.option("--framework", "-f", default="iso19650", help="Framework id.")
@click.option("--client", default="", help="Appointing party.")
@click.option("--reference", default="", help="Project reference / number.")
@click.option("--owner", default="", help="Information manager.")
@click.option("--stage", type=click.Choice(["delivery", "pre_appointment"]),
              default="delivery", show_default=True,
              help="Which ISO 19650-2 appointment stage this plan is written for.")
@pass_ctx
def new_project(ctx: Context, name: str, framework: str, client: str, reference: str,
                owner: str, stage: str) -> None:
    """Create a new BEP."""
    try:
        project = services.create_project(name, framework, client=client,
                                          reference=reference, owner=owner, stage=stage)
    except ServiceError as exc:
        fail(str(exc))
    click.secho(f"Created {project.slug}", fg="green")
    click.echo(f"  {project.name} · {project.framework_id} · {project.stage}")
    click.secho(f"  bep show {project.slug}", dim=True)


@cli.command("list")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@pass_ctx
def list_projects(ctx: Context, as_json: bool) -> None:
    """List every BEP with its current score."""
    projects = services.list_projects()
    if as_json:
        click.echo(json.dumps([
            {**p.to_dict(), "score": round(services.score_project(p).score, 1)}
            for p in projects
        ], indent=2, ensure_ascii=False))
        return
    if not projects:
        click.secho("No plans yet. Try: bep new \"My Project\" --framework iso19650", dim=True)
        return
    echo_header(f"{len(projects)} plan(s)")
    for project in projects:
        report = services.score_project(project)
        click.echo(
            f"  {meter(report.score, 18)} {click.style(f'{report.score:5.1f}', fg=tone_colour(report.score))}  "
            f"{click.style(project.slug.ljust(26), fg='cyan')} "
            f"{project.name[:34].ljust(34)} "
            + click.style(f"{report.maturity_label}"
                          + (" · pre-appointment" if project.stage == "pre_appointment" else "")
                          + (f" · {len(report.blockers)} blocking" if report.blockers else ""), dim=True)
        )
    click.echo()


def _project(slug: str) -> Project:
    try:
        return services.get_project(slug)
    except ServiceError as exc:
        fail(str(exc))


@cli.command("show")
@click.argument("slug")
@click.option("--section", "-s", default="", help="Show only this section.")
@click.option("--empty/--no-empty", default=True, help="Include unanswered fields.")
@pass_ctx
def show_project(ctx: Context, slug: str, section: str, empty: bool) -> None:
    """Print a plan's answers."""
    project = _project(slug)
    framework = ctx.framework(project)
    report = services.score_project(project)
    values = project.values()

    echo_header(f"{project.name}  ({project.slug})")
    click.echo(f"  {framework.name}  ·  score "
               + click.style(f"{report.score:.1f}/100", fg=tone_colour(report.score), bold=True)
               + click.style(f"  {report.maturity_label}", dim=True))

    for index, sec in enumerate(framework.sections, start=1):
        if section and sec.id != section:
            continue
        sscore = report.section(sec.id)
        click.echo(f"\n{click.style(f'{index:02d} {sec.title}', bold=True)}  "
                   + meter(sscore.score, 14) + click.style(f" {sscore.score:.0f}", dim=True))
        section_values = values.get(sec.id, {})
        for field in sec.fields:
            value = section_values.get(field.id)
            if value in (None, "", []) and not empty:
                continue
            label = f"   {field.label}"
            if value in (None, "", []):
                click.echo(label.ljust(42) + click.style("— not answered", dim=True))
            elif field.type == "table":
                click.echo(label.ljust(42) + click.style(f"{len(value)} row(s)", fg="cyan"))
            elif isinstance(value, list):
                click.echo(label.ljust(42) + ", ".join(str(v) for v in value)[:70])
            else:
                text = " ".join(str(value).split())
                click.echo(label.ljust(42) + (text[:70] + ("…" if len(text) > 70 else "")))
    click.echo()


@cli.command("set")
@click.argument("slug")
@click.argument("path")
@click.argument("value", required=False)
@click.option("--from-file", type=click.Path(exists=True, dir_okay=False),
              help="Read the value from a file (use for long prose or JSON tables).")
@pass_ctx
def set_field(ctx: Context, slug: str, path: str, value: str | None, from_file: str | None) -> None:
    """Set one field: bep set my-plan project_information.project_name "Riverside"."""
    project = _project(slug)
    if from_file:
        value = Path(from_file).read_text(encoding="utf-8")
    elif value is None:
        if sys.stdin.isatty():
            fail("provide a VALUE, --from-file, or pipe the value on stdin")
        value = sys.stdin.read()
    if "." not in path:
        fail(f"'{path}' is not a section.field path")
    section_id, field_id = path.split(".", 1)
    try:
        stored = services.set_value(project, section_id, field_id, value)
    except ServiceError as exc:
        fail(str(exc))
    report = services.score_project(project)
    preview = stored if not isinstance(stored, (list, dict)) else f"{len(stored)} row(s)"
    click.secho(f"{path} = {str(preview)[:60]}", fg="green")
    click.echo("  score now " + click.style(f"{report.score:.1f}", fg=tone_colour(report.score), bold=True))


@cli.command("clear")
@click.argument("slug")
@click.argument("path")
@pass_ctx
def clear_field(ctx: Context, slug: str, path: str) -> None:
    """Remove one answer."""
    project = _project(slug)
    if "." not in path:
        fail(f"'{path}' is not a section.field path")
    section_id, field_id = path.split(".", 1)
    services.clear_value(project, section_id, field_id)
    click.secho(f"cleared {path}", fg="green")


@cli.command("score")
@click.argument("slug")
@click.option("--json", "as_json", is_flag=True, help="Emit the full report as JSON.")
@click.option("--fail-under", type=float, default=None,
              help="Exit non-zero if the score is below this value (for CI gates).")
@click.option("--require-ready", is_flag=True,
              help="Exit non-zero unless the plan passes the issue gate.")
@click.option("--issues/--no-issues", default=True, help="List open issues.")
@click.option("--stage", type=click.Choice(["delivery", "pre_appointment"]), default=None,
              help="Score against this stage instead of the plan's own.")
@pass_ctx
def score_project(ctx: Context, slug: str, as_json: bool, fail_under: float | None,
                  require_ready: bool, issues: bool, stage: str | None) -> None:
    """Score a plan and show where the gaps are."""
    project = _project(slug)
    framework = ctx.framework(project)
    from ..scoring import evaluate

    report = evaluate(framework, project.values(), stage=stage or project.stage or None)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        counts = report.issue_counts()
        echo_header(f"{project.name}  ·  {framework.name}  ·  {report.stage or 'all stages'}")
        click.echo("  " + meter(report.score, 30) + "  "
                   + click.style(f"{report.score:.1f}/100", fg=tone_colour(report.score), bold=True))
        click.echo(f"  {click.style(report.maturity_label, bold=True)} — {report.maturity_note}")
        if report.next_band:
            click.secho(f"  +{report.next_band['gap']:.1f} to reach {report.next_band['label']}", dim=True)
        click.echo()
        click.echo(f"  coverage  {meter(report.coverage, 16)} {report.coverage:5.1f}%")
        click.echo(f"  required  {meter(report.required_coverage, 16)} {report.required_coverage:5.1f}%")
        click.echo(f"  fields    {report.fields_filled}/{report.fields_total} answered")
        gate = ("READY TO ISSUE", "green") if report.is_ready else ("NOT READY", "red")
        click.echo("  gate      " + click.style(gate[0], fg=gate[1], bold=True)
                   + click.style(f"   {counts['blocker']} blocking · {counts['major']} major · "
                                 f"{counts['minor']} minor", dim=True))

        echo_header("Sections")
        for index, section in enumerate(report.sections, start=1):
            click.echo(f"  {index:02d} " + meter(section.score, 18)
                       + click.style(f" {section.score:5.1f}", fg=tone_colour(section.score))
                       + f"  {section.title[:38].ljust(40)}"
                       + click.style(f"{section.required_complete}/{section.required_total} req", dim=True))

        if issues and report.issues:
            echo_header(f"Issues ({len(report.issues)})")
            for issue in report.issues[:40]:
                click.echo("  " + click.style(f"[{issue.severity:7}]", fg=SEVERITY_COLOUR.get(issue.severity, "white"))
                           + f" {issue.section_title or issue.section_id}: {issue.message}")
                if issue.detail:
                    click.secho(f"            {issue.detail}", dim=True)
            if len(report.issues) > 40:
                click.secho(f"  … and {len(report.issues) - 40} more", dim=True)

        if report.recommendations:
            echo_header("Highest-value gaps")
            for rec in report.recommendations:
                click.echo("  " + click.style(f"+{rec.points:4.1f}", fg="cyan")
                           + f"  {rec.path.ljust(46)} {rec.label}")
        click.echo()

    if fail_under is not None and report.score < fail_under:
        click.secho(f"score {report.score:.1f} is below the required {fail_under:.1f}", fg="red", err=True)
        sys.exit(2)
    if require_ready and not report.is_ready:
        click.secho("plan does not pass the issue gate", fg="red", err=True)
        sys.exit(3)


@cli.command("export")
@click.argument("slug")
@click.option("--format", "-f", "fmt", default="md",
              type=click.Choice(["md", "markdown", "html", "json", "docx", "word"]),
              help="Output format.")
@click.option("--out", "-o", type=click.Path(dir_okay=False), help="Write to a file instead of stdout.")
@click.option("--score/--no-score", default=True, help="Include the assessment section.")
@pass_ctx
def export_project(ctx: Context, slug: str, fmt: str, out: str | None, score: bool) -> None:
    """Export a plan as Markdown, printable HTML or JSON."""
    project = _project(slug)
    framework = ctx.framework(project)
    from ..exporters import extension, is_binary, render_bytes
    from ..scoring import evaluate

    report = evaluate(framework, project.values())
    try:
        body = render_bytes(fmt, project, framework, report, include_score=score)
    except (ValueError, RuntimeError) as exc:
        fail(str(exc))

    if not out and is_binary(fmt):
        out = f"BEP-{slugify(project.name)}.{extension(fmt)}"
    if out:
        Path(out).write_bytes(body)
        click.secho(f"wrote {out} ({len(body):,} bytes)", fg="green")
    else:
        click.echo(body.decode("utf-8"))


@cli.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@pass_ctx
def import_project(ctx: Context, path: str) -> None:
    """Import a plan from a JSON export."""
    payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        project = services.import_dict(payload)
    except ServiceError as exc:
        fail(str(exc))
    click.secho(f"imported as {project.slug}", fg="green")


@cli.command("snapshot")
@click.argument("slug")
@click.option("--label", "-l", default="", help="Name this snapshot.")
@pass_ctx
def snapshot(ctx: Context, slug: str, label: str) -> None:
    """Freeze the current answers and score."""
    project = _project(slug)
    snap = services.take_snapshot(project, label)
    click.secho(f"snapshot #{snap.id} at {snap.score:.1f}/100 ({snap.maturity_label})", fg="green")


@cli.command("delete")
@click.argument("slug")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@pass_ctx
def delete_project(ctx: Context, slug: str, yes: bool) -> None:
    """Delete a plan and everything in it."""
    project = _project(slug)
    if not yes:
        click.confirm(f"Delete '{project.name}' and all of its answers?", abort=True)
    services.delete_project(project)
    click.secho(f"deleted {slug}", fg="green")


@cli.command("demo")
@click.option("--name", default="Riverside Interchange — Phase 2", help="Name for the demo plan.")
@pass_ctx
def demo(ctx: Context, name: str) -> None:
    """Create a worked example so the scoring is easy to see."""
    from .demo_data import DEMO_VALUES

    try:
        project = services.create_project(
            name, "iso19650", client="City Transport Authority",
            reference="RIV-2026-002", owner="J. Salim",
        )
    except ServiceError as exc:
        fail(str(exc))
    services.set_values(project, DEMO_VALUES)
    report = services.score_project(project)
    click.secho(f"Created demo plan {project.slug} at {report.score:.1f}/100 "
                f"({report.maturity_label})", fg="green")
    click.secho(f"  bep score {project.slug}", dim=True)


# ---------------------------------------------------------------------------
# AI assistance
# ---------------------------------------------------------------------------

@cli.group("ai")
def ai_group() -> None:
    """Local model assistance (Ollama by default)."""


@ai_group.command("status")
@pass_ctx
def ai_status(ctx: Context) -> None:
    """Check that a model is reachable."""
    from ..ai import status

    info = status()
    if not info.get("enabled"):
        click.secho("AI assistance is disabled in the settings file.", fg="yellow")
        return
    if not info.get("reachable"):
        click.secho(f"unreachable: {info.get('reason')}", fg="red")
        click.secho(f"  provider {info.get('provider')} at {info.get('base_url')}", dim=True)
        sys.exit(1)
    click.secho(f"{info['provider']} at {info['base_url']}", fg="green")
    click.echo(f"  active model: {click.style(info['model'], bold=True)}")
    for name in info.get("models", []):
        click.echo("   " + ("• " if name == info["model"] else "  ") + name)


@cli.command("assist")
@click.argument("slug")
@click.argument("path")
@click.option("--mode", "-m", default="draft",
              type=click.Choice(["draft", "improve", "expand", "critique"]),
              help="What to ask the model for.")
@click.option("--instruction", "-i", default="", help="Extra instruction for this field.")
@click.option("--model", default=None, help="Override the configured model.")
@click.option("--apply", "apply_", is_flag=True, help="Write the suggestion into the plan.")
@pass_ctx
def assist(ctx: Context, slug: str, path: str, mode: str, instruction: str,
           model: str | None, apply_: bool) -> None:
    """Draft one field with a local model: bep assist my-plan risk.risk_process."""
    from ..ai import AIError, suggest

    project = _project(slug)
    framework = ctx.framework(project)
    resolved = framework.resolve(path)
    if resolved is None:
        fail(f"unknown field '{path}'")
    section, field = resolved

    values = project.values()
    try:
        result = suggest(
            project, framework, section, field, mode=mode,
            current_value=values.get(section.id, {}).get(field.id),
            language=ctx.lang, values=values, instruction=instruction, model=model,
        )
    except AIError as exc:
        fail(str(exc))

    echo_header(f"{field.label}  ({result['model']}, {result['elapsed_ms'] / 1000:.1f}s)")
    click.echo(result["text"])
    click.echo()

    if not apply_:
        click.secho("  not saved — re-run with --apply to write it into the plan", dim=True)
        return
    if not result.get("applicable", True):
        fail("this result cannot be applied automatically")
    value = result.get("rows", result["text"])
    services.set_value(project, section.id, field.id, value)
    report = services.score_project(project)
    click.secho(f"applied to {path}; score now {report.score:.1f}", fg="green")


# ---------------------------------------------------------------------------
# IFC models
# ---------------------------------------------------------------------------

@cli.group("ifc")
def ifc_group() -> None:
    """Attach and inspect IFC models."""


@ifc_group.command("import")
@click.argument("slug")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--discipline", default="", help="Label this model with a discipline.")
@pass_ctx
def ifc_import(ctx: Context, slug: str, path: str, discipline: str) -> None:
    """Attach an IFC file to a plan and tessellate it for the viewer."""
    project = _project(slug)
    with open(path, "rb") as handle:
        try:
            model = services.attach_model(project, handle, Path(path).name, discipline=discipline)
        except ServiceError as exc:
            fail(str(exc))
    click.secho(f"attached model #{model.id} — {model.schema}, "
                f"{model.element_count} elements", fg="green")
    meta = model.meta
    for name, count in list(meta.get("classes", {}).items())[:12]:
        click.echo(f"   {name.ljust(28)} {count}")
    if meta.get("truncated"):
        click.secho("  note: large model — only the first elements were tessellated", fg="yellow")


@ifc_group.command("list")
@click.argument("slug")
@pass_ctx
def ifc_list(ctx: Context, slug: str) -> None:
    """List the models attached to a plan."""
    project = _project(slug)
    models = services.list_models(project)
    if not models:
        click.secho("no models attached", dim=True)
        return
    echo_header(f"{len(models)} model(s)")
    for model in models:
        click.echo(f"  #{model.id}  {click.style(model.filename[:38].ljust(38), fg='cyan')} "
                   f"{model.schema.ljust(8)} {str(model.element_count).rjust(6)} elements  "
                   + click.style(model.status, dim=True))


@ifc_group.command("inspect")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@pass_ctx
def ifc_inspect(ctx: Context, path: str) -> None:
    """Show what is in an IFC file without attaching it."""
    from ..ifcio import IfcError, inspect_file

    try:
        info = inspect_file(path)
    except IfcError as exc:
        fail(str(exc))
    echo_header(f"{Path(path).name}  ({info['schema']})")
    click.echo(f"  project   {info['project_name'] or '—'}")
    click.echo(f"  units     {info['units'] or '—'}")
    click.echo(f"  storeys   {', '.join(info['storeys']) or '—'}")
    click.echo(f"  products  {info['element_count']}")
    click.echo()
    for name, count in list(info["classes"].items())[:20]:
        click.echo(f"   {name.ljust(30)} {count}")


@ifc_group.command("remove")
@click.argument("slug")
@click.argument("model_id", type=int)
@pass_ctx
def ifc_remove(ctx: Context, slug: str, model_id: int) -> None:
    """Detach a model and delete its files."""
    project = _project(slug)
    try:
        model = services.get_model(project, model_id)
    except ServiceError as exc:
        fail(str(exc))
    services.delete_model(project, model)
    click.secho(f"removed model #{model_id}", fg="green")


@cli.command("config")
@click.option("--json", "as_json", is_flag=True, help="Print the merged settings.")
@pass_ctx
def show_config(ctx: Context, as_json: bool) -> None:
    """Show where settings come from and what they resolve to."""
    from ..settings import override_paths, settings

    if as_json:
        click.echo(json.dumps(settings(), indent=2, ensure_ascii=False))
        return
    echo_header("Settings")
    click.echo("  defaults  " + str(Path(__file__).resolve().parent.parent / "config_files" / "defaults.json"))
    overrides = override_paths()
    if overrides:
        for path in overrides:
            click.echo("  override  " + str(path))
    else:
        click.secho("  no overrides (set BEP_CONFIG or add ./bep.config.json)", dim=True)
    click.echo()
    for key in ("ai.provider", "ai.base_url", "ai.model", "viewer.enabled",
                "viewer.default_mode", "viewer.lod.default", "ui.split_ratio",
                "scoring.ready_score"):
        from ..settings import get as setting

        click.echo(f"  {key.ljust(24)} {setting(key)}")
    click.echo()


# ---------------------------------------------------------------------------
# IDS
# ---------------------------------------------------------------------------

@cli.group("ids")
def ids_group() -> None:
    """Export the plan's information requirements as buildingSMART IDS."""


@ids_group.command("export")
@click.argument("slug")
@click.option("--out", "-o", type=click.Path(dir_okay=False), help="Write to a file.")
@click.option("--ifc-version", multiple=True, help="Target schema, repeatable (IFC4, IFC2X3).")
@pass_ctx
def ids_export(ctx: Context, slug: str, out: str | None, ifc_version: tuple[str, ...]) -> None:
    """Turn the level of information need table into an .ids file."""
    from ..ids import IdsError, build

    project = _project(slug)
    framework = ctx.framework(project)
    try:
        result = build(project, framework, project.values(),
                       ifc_version=list(ifc_version) or None)
    except IdsError as exc:
        fail(str(exc))

    if out:
        Path(out).write_text(result.xml, encoding="utf-8")
        click.secho(f"wrote {out} — {result.specifications} specification(s)", fg="green")
    else:
        click.echo(result.xml)
        return

    for item in result.inferred:
        click.secho(f"  row {item.row}: {item.element} — {item.reason}", fg="yellow")
    for item in result.skipped:
        click.secho(f"  row {item.row}: {item.element} — {item.reason}", fg="red")
    if result.inferred:
        click.secho("  inferred classes are a guess; set the IFC Class column to be sure",
                    dim=True)


@ids_group.command("check")
@click.argument("slug")
@click.argument("model", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option("--model-id", type=int, help="Check an attached model instead of a file.")
@click.option("--fail-on-error", is_flag=True, help="Exit non-zero if any specification fails.")
@pass_ctx
def ids_check(ctx: Context, slug: str, model: str | None, model_id: int | None,
              fail_on_error: bool) -> None:
    """Validate an IFC against the requirements the plan states."""
    from ..ids import IdsError, build, validate_against

    project = _project(slug)
    framework = ctx.framework(project)

    if not model:
        models = services.list_models(project)
        if model_id is not None:
            models = [m for m in models if m.id == model_id]
        if not models:
            fail("no IFC given and none attached to this plan")
        model = models[0].source_path

    try:
        result = build(project, framework, project.values())
        report = validate_against(result.xml, model)
    except IdsError as exc:
        fail(str(exc))

    echo_header(f"{project.name} — IDS check against {Path(model).name}")
    for spec in report["results"]:
        mark = click.style("PASS", fg="green") if spec["passed"] else click.style("FAIL", fg="red")
        click.echo(f"  {mark}  {spec['identifier']}  {spec['name'][:40].ljust(40)}"
                   + click.style(f"{spec['applicable']} applicable, {spec['failures']} failing",
                                 dim=True))
    click.echo()
    click.echo(f"  {report['passed']}/{report['specifications']} specifications satisfied")
    if fail_on_error and report["failed"]:
        sys.exit(4)


@cli.command("diff")
@click.argument("slug")
@click.argument("before", required=False)
@click.argument("after", required=False)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option("--full", is_flag=True, help="Show the text on both sides.")
@pass_ctx
def diff_plan(ctx: Context, slug: str, before: str | None, after: str | None,
              as_json: bool, full: bool) -> None:
    """Compare two versions: bep diff <plan> [<snapshot-id>] [<snapshot-id>|current]."""
    project = _project(slug)
    snapshots = {str(s.id): s for s in project.snapshots}
    if not snapshots:
        fail("this plan has no snapshots yet; take one with: bep snapshot <plan>")

    ordered = sorted(snapshots.values(), key=lambda s: s.id)
    if before is None:
        before_snap, after_snap = ordered[-1], None          # latest vs current
    else:
        if before not in snapshots:
            fail(f"no snapshot {before} (have: {', '.join(sorted(snapshots))})")
        before_snap = snapshots[before]
        if after in (None, "current"):
            after_snap = None
        elif after in snapshots:
            after_snap = snapshots[after]
        else:
            fail(f"no snapshot {after} (use an id, or 'current')")

    if after_snap is None:
        report = services.compare_snapshot_to_current(project, before_snap)
    else:
        report = services.compare_snapshots(project, before_snap, after_snap)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    delta = report.score_delta
    colour = "green" if delta > 0 else ("red" if delta < 0 else "white")
    echo_header(f"{report.label_before}  →  {report.label_after}")
    click.echo("  " + meter(report.score_before, 14) + f" {report.score_before:5.1f}"
               + "   →   " + meter(report.score_after, 14)
               + click.style(f" {report.score_after:5.1f}", bold=True)
               + click.style(f"   {delta:+.1f}", fg=colour, bold=True))
    counts = report.counts()
    click.secho(f"  {counts['added']} added · {counts['changed']} changed · "
                f"{counts['removed']} removed", dim=True)

    if not report.sections:
        click.secho("\n  nothing changed", dim=True)
        return

    for section in report.sections:
        click.echo(f"\n{click.style(section.title, bold=True)}  "
                   + click.style(f"{section.score_before:.0f} → {section.score_after:.0f} "
                                 f"({section.score_delta:+.1f})",
                                 fg="green" if section.score_delta > 0
                                 else ("red" if section.score_delta < 0 else "white")))
        for change in section.changes:
            mark = {"added": ("+", "green"), "removed": ("-", "red"),
                    "changed": ("~", "yellow")}[change.status]
            click.echo(f"  {click.style(mark[0], fg=mark[1])} {change.label[:38].ljust(38)}"
                       + click.style(change.detail, dim=True))
            if full and change.status != "removed":
                text = change.after if not isinstance(change.after, list) else \
                    f"{len(change.after)} rows"
                click.secho(f"      {str(text)[:160]}", dim=True)
    click.echo()


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", "-p", default=int(os.environ.get("PORT", 8080)), show_default=True)
@click.option("--debug", is_flag=True, help="Reload on change and show tracebacks.")
@pass_ctx
def serve(ctx: Context, host: str, port: int, debug: bool) -> None:
    """Run the web interface."""
    click.secho(f"BEP Bench on http://{host}:{port}", fg="cyan", bold=True)
    ctx.app.run(host=host, port=port, debug=debug, use_reloader=debug)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
