"""Version comparison."""

from bepkit import services
from bepkit.services.diff import compare
from bepkit.schema import get_framework

FW = get_framework("iso19650")


def _vals(**over):
    base = {
        "project_information": {"project_name": "Riverside"},
        "objectives_uses": {"bim_goals": "word " * 90},
    }
    for path, value in over.items():
        section, field_id = path.split("__", 1)
        base.setdefault(section, {})[field_id] = value
    return base


def test_added_changed_and_removed_are_told_apart():
    before = _vals()
    after = _vals(objectives_uses__bim_goals="word " * 120,
                  risk__risk_process="Reviewed fortnightly by the delivery team.")
    del after["project_information"]["project_name"]

    report = compare(FW, before, after)
    by_path = {c.path: c for s in report.sections for c in s.changes}

    assert by_path["risk.risk_process"].status == "added"
    assert by_path["objectives_uses.bim_goals"].status == "changed"
    assert by_path["project_information.project_name"].status == "removed"
    assert report.counts() == {"added": 1, "changed": 1, "removed": 1}


def test_identical_answers_produce_no_changes():
    report = compare(FW, _vals(), _vals())
    assert report.total_changes == 0
    assert report.score_delta == 0


def test_whitespace_alone_is_not_a_change():
    report = compare(FW, _vals(project_information__project_name="Riverside"),
                     _vals(project_information__project_name="  Riverside  "))
    assert report.total_changes == 0


def test_table_changes_are_counted_in_rows():
    rows = [{"revision": "P01", "date": "2026-01-01", "author": "JS",
             "summary": "First", "approved_by": ""}]
    before = _vals(project_information__revision_history=rows)
    after = _vals(project_information__revision_history=rows + [
        {"revision": "P02", "date": "2026-02-01", "author": "JS",
         "summary": "Second", "approved_by": ""}])

    change = next(c for s in compare(FW, before, after).sections for c in s.changes)
    assert change.status == "changed"
    assert "1 row(s) added" in change.detail


def test_prose_change_reports_the_word_count_movement():
    report = compare(FW, _vals(), _vals(objectives_uses__bim_goals="word " * 150))
    change = next(c for s in report.sections for c in s.changes)
    assert "90 → 150 words" in change.detail


def test_section_score_movement_explains_the_overall_delta():
    before = _vals()
    after = _vals(risk__risk_process="Reviewed fortnightly by the delivery team meeting.")
    report = compare(FW, before, after)

    assert report.score_delta > 0
    risk = next(s for s in report.sections if s.id == "risk")
    assert risk.score_delta > 0


def test_diff_respects_the_appointment_stage():
    """A delivery-only field cannot show up in a tender-stage diff."""
    before = _vals()
    after = _vals(delivery_strategy__midp_approach="Aggregated fortnightly. " * 12)

    assert compare(FW, before, after, stage="delivery").total_changes == 1
    assert compare(FW, before, after, stage="pre_appointment").total_changes == 0


def test_snapshot_round_trip(app):
    from bepkit.cli.demo_data import DEMO_VALUES

    project = services.create_project("Riverside", "iso19650")
    services.set_values(project, DEMO_VALUES)
    snapshot = services.take_snapshot(project, "P02")
    services.set_value(project, "risk", "risk_process",
                       "Reviewed fortnightly at the delivery team meeting.")

    report = services.compare_snapshot_to_current(project, snapshot)
    assert report.label_before == "P02"
    assert report.label_after == "current"
    assert report.score_delta > 0
    assert report.counts()["added"] == 1
