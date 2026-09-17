import pytest

from bepkit import services
from bepkit.schema import get_framework


def test_create_seeds_the_identity_fields(project):
    values = project.values()
    assert values["project_information"]["project_name"] == "Test Plan"
    assert values["project_information"]["appointing_party"] == "Acme"


def test_slugs_do_not_collide(app):
    first = services.create_project("Riverside", "lite")
    second = services.create_project("Riverside", "lite")
    assert first.slug != second.slug


def test_unknown_framework_is_refused(app):
    with pytest.raises(services.ServiceError):
        services.create_project("Nope", "not-a-framework")


def test_select_values_are_validated(project):
    with pytest.raises(services.ServiceError):
        services.set_value(project, "project_information", "bep_status", "Whenever")
    services.set_value(project, "project_information", "bep_status", "approved")  # case-insensitive
    assert project.values()["project_information"]["bep_status"] == "Approved"


def test_table_rows_are_cleaned_to_the_declared_columns(project):
    services.set_value(project, "project_information", "revision_history", [
        {"revision": "P01", "date": "2026-01-01", "author": "JS",
         "summary": "First", "approved_by": "MK", "junk": "dropped"},
        {"revision": "", "date": "", "author": "", "summary": "", "approved_by": ""},
    ])
    rows = project.values()["project_information"]["revision_history"]
    assert len(rows) == 1                      # the blank row is discarded
    assert "junk" not in rows[0]


def test_set_values_rejects_a_bad_path(project):
    with pytest.raises(services.ServiceError):
        services.set_values(project, {"no_dot_here": "x"})


def test_export_import_round_trip(app, project):
    services.set_value(project, "objectives_uses", "bim_goals", "Goal text " * 20)
    payload = services.export_dict(project)

    payload["project"]["name"] = "Copy"
    payload["project"]["slug"] = None
    copy = services.import_dict(payload)

    assert copy.slug != project.slug
    assert copy.values()["objectives_uses"]["bim_goals"] == project.values()["objectives_uses"]["bim_goals"]
    assert services.score_project(copy).score == pytest.approx(services.score_project(project).score)


def test_import_skips_fields_the_framework_no_longer_has(app):
    payload = {
        "project": {"name": "Legacy", "framework": "lite"},
        "values": {"basics": {"project_name": "X", "removed_field": "y"},
                   "ghost_section": {"a": "b"}},
    }
    imported = services.import_dict(payload)
    assert imported.values()["basics"]["project_name"] == "X"
    assert "ghost_section" not in imported.values()
    assert "skipped" in imported.notes


def test_snapshot_and_restore(app, project):
    services.set_value(project, "objectives_uses", "bim_goals", "First version " * 10)
    snapshot = services.take_snapshot(project, "before rewrite")
    services.set_value(project, "objectives_uses", "bim_goals", "Second version")

    services.restore_snapshot(project, snapshot)
    assert project.values()["objectives_uses"]["bim_goals"].startswith("First version")
    assert snapshot.score > 0


def test_clear_value_removes_the_answer(project):
    services.clear_value(project, "project_information", "project_name")
    assert "project_name" not in project.values().get("project_information", {})


def test_score_uses_the_project_framework(project):
    report = services.score_project(project)
    assert report.framework_id == "iso19650"
    assert report.fields_total == get_framework("iso19650").total_fields
