"""Guardrails for the browser code, which nothing else in the suite exercises."""

import json
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "bepkit" / "web" / "static"
TEMPLATES = Path(__file__).resolve().parent.parent / "bepkit" / "web" / "templates"


@pytest.mark.parametrize("name", ["app.js", "assist.js", "viewer.js", "workspace.js"])
def test_scripts_parse(name):
    esprima = pytest.importorskip("esprima")
    esprima.parseScript((STATIC / "js" / name).read_text(encoding="utf-8"))


def test_three_js_is_vendored_not_hotlinked():
    """The viewer must work on a machine with no internet access."""
    bundle = STATIC / "vendor" / "three.min.js"
    assert bundle.is_file() and bundle.stat().st_size > 100_000
    for template in TEMPLATES.glob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert "https://cdn" not in text, f"{template.name} loads an external asset"
        assert "http://" not in text.replace("http://www.w3.org", ""), template.name


def test_every_translated_key_exists_in_both_catalogues():
    from bepkit.i18n import CATALOG

    assert set(CATALOG["en"]) == set(CATALOG["ko"])
    assert not [k for k, v in CATALOG["ko"].items() if not v.strip()]


def test_templates_only_use_known_translation_keys():
    from bepkit.i18n import CATALOG

    # Only literal calls, t('a.b'); the concatenated ones are checked below.
    pattern = re.compile(r"""\bt\(\s*['"]([a-z0-9_.]+)['"]\s*\)""")
    used = set()
    for template in TEMPLATES.glob("*.html"):
        used |= set(pattern.findall(template.read_text(encoding="utf-8")))
    assert used, "no translation keys found — the scan is broken"
    unknown = {k for k in used if k not in CATALOG["en"]}
    assert not unknown, f"templates use undefined keys: {sorted(unknown)}"

    # Keys built by concatenation, e.g. t('editor.state.' ~ state)
    for prefix, suffixes in {"editor.state.": ["complete", "partial", "empty"],
                             "ai.mode.": ["draft", "improve", "expand", "critique"]}.items():
        for suffix in suffixes:
            assert prefix + suffix in CATALOG["en"], prefix + suffix


def test_viewer_defaults_are_valid_json_and_self_consistent():
    from bepkit.settings import get as setting

    modes = setting("viewer.modes")
    assert setting("viewer.default_mode") in {m["id"] for m in modes}
    levels = setting("viewer.lod.levels")
    assert str(setting("viewer.lod.default")) in levels
    for level, spec in levels.items():
        assert spec["geometry"] in {"mesh", "bbox"}, level
        assert isinstance(spec.get("include", []), list)
    palette = setting("viewer.palette")
    assert "default" in palette
    assert all(re.fullmatch(r"#[0-9a-fA-F]{6}", colour) for colour in palette.values())


def test_lod_section_map_points_at_real_fields():
    from bepkit.schema import get_framework
    from bepkit.settings import get as setting

    for framework_id, spec in (setting("viewer.lod.sections") or {}).items():
        if framework_id.startswith("_"):
            continue
        framework = get_framework(framework_id)
        section = framework.section_by_id(spec["section"])
        assert section is not None, framework_id
        field = section.field_by_id(spec["field"])
        assert field is not None, framework_id
        column = spec.get("column")
        if column:
            assert column in {c.id for c in field.columns}, framework_id


def test_editor_is_a_fixed_height_app_shell():
    """The workspace must not scroll as one document.

    Four panes that scroll together defeat the point of putting the plan, the
    model and the properties side by side: reading the plan pushes the model off
    screen. The editor opts into a viewport-height shell; every other page keeps
    ordinary page scrolling.
    """
    editor = (TEMPLATES / "editor.html").read_text(encoding="utf-8")
    assert "{% block body_class %}app-shell{% endblock %}" in editor

    for other in ("score.html", "preview.html", "settings.html", "dashboard.html"):
        assert "app-shell" not in (TEMPLATES / other).read_text(encoding="utf-8"), other

    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    assert "body.app-shell { overflow: hidden; }" in css
    assert "height: calc(100vh - 56px);" in css          # workspace fills the viewport
    # each pane carries its own scrollbar
    assert "overflow-y: auto; overscroll-behavior: contain;" in css
    # and the stacked breakpoint hands scrolling back to the page
    assert "body.app-shell { overflow: auto; }" in css


def test_the_page_container_class_is_never_used_as_a_flex_modifier():
    """`.wrap` is the page container and carries 100px of vertical padding.

    Using it as the flex-wrap modifier on `.row` silently gave every such row
    that padding, inflating cards by 100px. The modifier has its own name.
    """
    for template in TEMPLATES.glob("*.html"):
        markup = template.read_text(encoding="utf-8")
        assert 'class="row wrap"' not in markup, template.name
        assert 'row wrap"' not in markup, template.name

    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    assert ".row.rowwrap { flex-wrap: wrap;" in css
    assert ".row.wrap {" not in css
