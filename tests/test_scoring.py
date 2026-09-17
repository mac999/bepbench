from bepkit.schema import get_framework
from bepkit.scoring import evaluate, score_field
from bepkit.scoring.rules import is_placeholder

FW = get_framework("iso19650")


def field(path):
    return FW.resolve(path)[1]


def test_empty_plan_scores_zero():
    report = evaluate(FW, {})
    assert report.score == 0
    assert report.coverage == 0
    assert report.maturity_level == 0
    assert not report.is_ready


def test_placeholder_text_earns_almost_nothing():
    real = score_field("project_information", field("project_information.project_name"), "Riverside")
    tbd = score_field("project_information", field("project_information.project_name"), "TBD")
    assert real.score == 1.0
    assert tbd.score < 0.2
    assert "placeholder" in tbd.detail.lower()
    assert is_placeholder("n/a") and is_placeholder("???") and not is_placeholder("nave")


def test_prose_depth_is_graded_not_binary():
    f = field("project_information.project_description")  # expects ~60 words
    short = score_field("project_information", f, "A small bridge project.")
    full = score_field("project_information", f, " ".join(["word"] * 60))
    assert 0 < short.score < full.score == 1.0
    assert short.state == "partial"


def test_table_score_combines_row_count_and_required_cells():
    f = field("objectives_uses.bim_uses")  # expects 5 rows
    complete_row = {"use": "3D coordination", "priority": "Core", "owner": "BIM team",
                    "stage": "3", "output": "Clash report"}
    thin = score_field("objectives_uses", f, [complete_row])
    full = score_field("objectives_uses", f, [complete_row] * 5)
    holes = score_field("objectives_uses", f, [{**complete_row, "owner": ""}] * 5)

    assert thin.score < full.score == 1.0
    assert holes.score < full.score
    assert "blank" in holes.detail.lower()


def test_required_field_left_empty_is_a_blocker():
    report = evaluate(FW, {})
    blockers = {i.id for i in report.blockers}
    assert "required:project_information.project_name" in blockers


def test_cross_field_check_fires_on_unowned_bim_use():
    values = {"objectives_uses": {"bim_uses": [
        {"use": "3D coordination", "priority": "Core", "owner": "", "stage": "3", "output": "Report"},
    ]}}
    report = evaluate(FW, values)
    assert "uses_have_owners" in {i.id for i in report.issues}


def test_values_cover_check_wants_every_task_team_in_the_tidp():
    values = {
        "team_roles": {"task_teams": [
            {"team": "Architecture", "discipline": "A", "scope": "s", "lead": "x"},
            {"team": "Structures", "discipline": "S", "scope": "s", "lead": "y"},
        ]},
        "delivery_strategy": {"tidp_summary": [
            {"team": "Architecture", "container": "c", "format": "IFC",
             "milestone": "m", "author": "a", "reviewer": "r"},
        ]},
    }
    issue = next(i for i in evaluate(FW, values).issues if i.id == "tidp_teams_covered")
    assert "Structures" in issue.detail


def test_recommendations_are_ranked_by_recoverable_points():
    report = evaluate(FW, {})
    points = [r.points for r in report.recommendations]
    assert points == sorted(points, reverse=True)
    assert sum(points) > 0


def test_demo_plan_is_issue_ready():
    from bepkit.cli.demo_data import DEMO_VALUES

    values: dict = {}
    for path, value in DEMO_VALUES.items():
        section, fid = path.split(".", 1)
        values.setdefault(section, {})[fid] = value

    report = evaluate(FW, values)
    assert report.score > 80
    assert not report.blockers
    assert report.is_ready


def test_exporters_agree_on_what_is_available():
    from bepkit import exporters

    ids = {entry["id"] for entry in exporters.available()}
    assert ids == {"docx", "md", "html", "json"}
    assert exporters.normalise("word") == "docx"
    assert exporters.is_binary("docx") and not exporters.is_binary("md")
