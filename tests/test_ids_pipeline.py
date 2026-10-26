"""IDS as a pipeline: settings-driven output, schema checks, milestones, models.

A plan relates to IDS documents and IFC models one-to-many, so these tests cover
the cut by milestone, the check of every attached model in its own schema, and
that the CLI, the HTTP API and the settings file all name the same options.
"""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from bepkit.ids import IFCTESTER_AVAILABLE, IdsError

pytestmark = pytest.mark.skipif(not IFCTESTER_AVAILABLE, reason="ifctester not installed")

DUPLEX = Path(__file__).resolve().parent.parent / "docs" / "demo" / "Duplex_A.ifc"


class FakeProject:
    name = "Riverside"
    client = "City Transport Authority"
    reference = "RIV-2026-002"
    owner = "J. Salim"


def _framework():
    from bepkit.schema import get_framework

    return get_framework("iso19650")


def _values(rows, classification="Uniclass 2015 — tables Ss, Pr"):
    return {"information_requirements": {"loin": rows},
            "standards_methods": {"classification": classification}}


def _build(rows, **options):
    from bepkit.ids import build

    return build(FakeProject(), _framework(), _values(rows), **options)


ROAD = {"element": "Highway realignment", "stage": "3", "alphanumeric": "Course thickness"}
WALL = {"element": "External wall", "ifc_class": "IfcWall", "stage": "4", "alphanumeric": "Grade"}
DOOR = {"element": "Doors", "ifc_class": "IfcDoor", "stage": "4",
        "alphanumeric": "Pset_DoorCommon.FireRating"}


# --------------------------------------------------------------------------
# schema awareness
# --------------------------------------------------------------------------

def test_a_class_the_target_schema_lacks_is_reported_not_exported():
    # IfcCourse exists only in IFC4X3: aimed at IFC4 it would match nothing and pass.
    result = _build([ROAD, WALL], ifc_version=["IFC2X3", "IFC4"])
    assert result.specifications == 1
    assert "IfcCourse is not defined in IFC2X3, IFC4" in result.skipped[0].reason


def test_a_specification_is_narrowed_to_the_schemas_that_define_its_class():
    result = _build([ROAD], ifc_version=["IFC4", "IFC4X3_ADD2"])
    assert result.specifications == 1
    assert "exists only in IFC4X3_ADD2" in result.narrowed[0].reason
    assert 'ifcVersion="IFC4X3_ADD2"' in result.xml


def test_schema_names_are_read_through_the_configured_aliases():
    result = _build([ROAD], ifc_version=["ifc4x3"])
    assert result.ifc_version == ["IFC4X3_ADD2"]


def test_an_unknown_schema_is_refused_by_name():
    with pytest.raises(IdsError, match="unknown IFC schema 'IFC9'"):
        _build([WALL], ifc_version=["IFC9"])


# --------------------------------------------------------------------------
# milestones: one plan, one IDS per milestone
# --------------------------------------------------------------------------

def test_a_milestone_keeps_only_its_own_rows():
    result = _build([ROAD, WALL, DOOR], ifc_version=["IFC4"], milestone="4")
    assert result.specifications == 2
    assert result.milestone == "4"
    assert "<milestone>4</milestone>" in result.xml


def test_an_unknown_milestone_names_the_ones_that_exist():
    with pytest.raises(IdsError, match=r"milestone '9'.*3, 4"):
        _build([ROAD, WALL], milestone="9")


def test_milestones_come_back_in_natural_order():
    from bepkit.ids import milestones

    rows = [dict(WALL, stage=s) for s in ("10", "3", "4", "3")]
    assert milestones("iso19650", _values(rows)) == ["3", "4", "10"]


def test_the_default_milestone_is_a_setting():
    from bepkit.settings import override

    override("ids.milestone", "4")
    assert _build([ROAD, WALL, DOOR], ifc_version=["IFC4"]).specifications == 2


# --------------------------------------------------------------------------
# property sets
# --------------------------------------------------------------------------

def test_a_qualified_property_is_required_in_its_own_set():
    result = _build([dict(DOOR, alphanumeric="Pset_DoorCommon.FireRating, acoustic rating")])
    assert result.default_pset_properties == 1
    assert "Pset_DoorCommon" in result.xml and "FireRating" in result.xml
    assert "BEP_Requirements" in result.xml and "AcousticRating" in result.xml


def test_text_with_a_full_stop_is_not_mistaken_for_a_property_set():
    from bepkit.ids import split_qualified

    assert split_qualified("Rev. no") == (None, "Rev. no")
    assert split_qualified("Pset_WallCommon.IsExternal") == ("Pset_WallCommon", "IsExternal")


def test_the_default_set_can_be_named_per_run():
    assert "Client_Data" in _build([WALL], default_pset="Client_Data").xml


# --------------------------------------------------------------------------
# nothing hardcoded: every value written comes from settings
# --------------------------------------------------------------------------

def test_document_values_come_from_settings():
    from bepkit.settings import override

    override("ids.data_type", "IFCTEXT")
    override("ids.identifier_format", "REQ-{index}")
    override("ids.required_attributes", [])
    override("ids.title_format", "{project} requirements")
    result = _build([WALL])
    assert "IFCTEXT" in result.xml
    assert result.identifiers == ["REQ-1"]
    assert "Riverside requirements" in result.xml
    assert "<ids:attribute" not in result.xml


def test_the_classification_source_is_a_setting():
    from bepkit.settings import override

    assert "Uniclass 2015" in _build([WALL]).xml
    override("ids.sources.iso19650.classification", {})
    assert "Uniclass" not in _build([WALL]).xml


# --------------------------------------------------------------------------
# checking real models
# --------------------------------------------------------------------------

@pytest.fixture()
def plan(app):
    from bepkit import services

    project = services.create_project("Duplex", "iso19650")
    services.set_values(project, {"information_requirements.loin": [DOOR, ROAD]})
    return project


def test_file_schema_is_read_from_the_header():
    from bepkit.services import file_schema

    assert file_schema(str(DUPLEX)) == "IFC2X3"


def test_a_model_is_checked_in_its_own_schema(plan):
    from bepkit import services

    report = services.check_ids(plan, model_path=str(DUPLEX))
    entry = report["models"][0]
    assert entry["schema"] == "IFC2X3" and entry["ifc_version"] == ["IFC2X3"]
    # the road row cannot apply to an IFC2X3 model, so it is reported, not passed
    assert any("IfcCourse" in s["reason"] for s in entry["build"]["skipped"])
    assert report["specifications"] == 1


def test_a_standard_property_set_is_what_a_real_model_carries(plan):
    """The Duplex doors carry Pset_DoorCommon.FireRating; a private set fails them all."""
    from bepkit import services

    qualified = services.check_ids(plan, model_path=str(DUPLEX))
    assert qualified["passed"] == 1 and qualified["results"][0]["applicable"] > 0

    services.set_values(plan, {"information_requirements.loin": [
        dict(DOOR, alphanumeric="FireRating")]})
    unqualified = services.check_ids(plan, model_path=str(DUPLEX))
    assert unqualified["failed"] == 1


def test_a_specification_with_nothing_to_check_is_not_counted_as_passed(plan):
    """Duplex has no lifts: the spec passes in IDS terms but has checked nothing."""
    from bepkit import services

    services.set_values(plan, {"information_requirements.loin": [
        DOOR, dict(DOOR, element="Lift cores", ifc_class="IfcTransportElement")]})
    report = services.check_ids(plan, model_path=str(DUPLEX))
    statuses = {r["name"]: r["status"] for r in report["results"]}
    assert statuses == {"Doors": "passed", "Lift cores": "not_applicable"}
    assert (report["passed"], report["failed"], report["not_applicable"]) == (1, 0, 1)


def test_an_explicit_schema_beats_the_model_and_says_so(plan):
    from bepkit import services

    report = services.check_ids(plan, model_path=str(DUPLEX), ifc_version=["IFC4"])
    assert report["models"][0]["ifc_version"] == ["IFC4"]
    assert "the model is IFC2X3" in report["models"][0]["warning"]


def test_every_attached_model_is_checked(plan):
    from bepkit import services

    for discipline in ("Architecture", "Interiors"):
        with open(DUPLEX, "rb") as handle:
            services.attach_model(plan, handle, "Duplex_A.ifc", discipline=discipline)
    report = services.check_ids(plan)
    assert len(report["models"]) == 2
    assert report["specifications"] == 2

    first = services.list_models(plan)[0].id
    assert len(services.check_ids(plan, model_ids=[first])["models"]) == 1
    with pytest.raises(IdsError, match="no attached model with id 999"):
        services.check_ids(plan, model_ids=[999])


def test_no_model_is_explained(plan):
    from bepkit import services

    with pytest.raises(IdsError, match="attach an IFC model"):
        services.check_ids(plan)


# --------------------------------------------------------------------------
# CLI: same names as the settings and the API
# --------------------------------------------------------------------------

@pytest.fixture()
def cli(monkeypatch):
    monkeypatch.setenv("BEP_DATA_DIR", tempfile.mkdtemp(prefix="bep-ids-cli-"))
    from bepkit.cli import cli as command

    runner = CliRunner()

    def run(*args):
        return runner.invoke(command, list(args), catch_exceptions=False)

    run("new", "Duplex", "--framework", "iso19650")
    run("set", "duplex", "information_requirements.loin", json.dumps([DOOR, WALL, ROAD]))
    return run


def test_cli_lists_milestones(cli):
    result = cli("ids", "milestones", "duplex", "--json")
    assert json.loads(result.output) == {"column": "stage", "milestones": ["3", "4"],
                                          "default": ""}


def test_cli_splits_one_document_per_milestone(cli, tmp_path):
    result = cli("ids", "export", "duplex", "--split", "-o", str(tmp_path),
                 "--ifc-version", "IFC4X3_ADD2", "--json")
    assert result.exit_code == 0
    files = json.loads(result.output)["files"]
    assert sorted(Path(f["path"]).name for f in files) == ["duplex-3.ids", "duplex-4.ids"]
    assert all(Path(f["path"]).is_file() for f in files)


def test_cli_set_overrides_any_setting(cli):
    result = cli("--set", "ids.default_pset=Site_Data", "ids", "export", "duplex",
                 "--milestone", "4", "--json")
    assert result.exit_code == 0
    assert "Site_Data" in json.loads(result.output)["xml"]


def test_cli_rejects_a_malformed_set(cli):
    client = CliRunner()
    from bepkit.cli import cli as command

    result = client.invoke(command, ["--set", "nonsense", "frameworks"])
    assert result.exit_code != 0
    assert "key=value" in result.output


def test_cli_check_reports_json_and_gates(cli):
    result = cli("ids", "check", "duplex", str(DUPLEX), "--json")
    report = json.loads(result.output)
    assert report["models"][0]["schema"] == "IFC2X3"

    gated = cli("--set", "ids.data_type=IFCBOOLEAN", "ids", "check", "duplex", str(DUPLEX),
                "--milestone", "4", "--fail-on-error")
    assert gated.exit_code == 4


def test_cli_config_summary_comes_from_settings(cli):
    result = cli("--set", 'cli.config_summary_keys=["ids.data_type"]', "config")
    assert "ids.data_type" in result.output
    assert "ai.model" not in result.output


# --------------------------------------------------------------------------
# HTTP API: the same option names
# --------------------------------------------------------------------------

def test_api_lists_milestones_and_exports_one(client, plan):
    info = client.get(f"/api/projects/{plan.slug}/ids/milestones").get_json()
    assert info["milestones"] == ["3", "4"]

    response = client.get(f"/api/projects/{plan.slug}/ids?milestone=4&ifc_version=IFC4")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].endswith('duplex-4.ids"')

    report = client.get(f"/api/projects/{plan.slug}/ids?report=1&ifc_version=IFC4X3_ADD2"
                        "&default_pset=Site_Data").get_json()
    assert report["ifc_version"] == ["IFC4X3_ADD2"] and report["specifications"] == 2


def test_the_editor_offers_a_requirements_tab_linked_to_the_loin_table(client, plan):
    page = client.get(f"/p/{plan.slug}/s/project_information").get_data(as_text=True)
    assert 'data-tab="requirements"' in page
    assert f'data-loin-url="/p/{plan.slug}/s/information_requirements#field-loin"' in page


def test_api_check_covers_every_attached_model(client, plan):
    from bepkit import services

    assert client.post(f"/api/projects/{plan.slug}/ids/check", json={}).status_code == 422
    with open(DUPLEX, "rb") as handle:
        services.attach_model(plan, handle, "Duplex_A.ifc")
    report = client.post(f"/api/projects/{plan.slug}/ids/check", json={}).get_json()
    assert [m["model"] for m in report["models"]] == ["Duplex_A.ifc"]
    assert report["models"][0]["ifc_version"] == ["IFC2X3"]
