"""CLI surface. The runner drives the same services the web app uses."""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner


@pytest.fixture()
def runner(monkeypatch):
    # Each run gets its own database so tests cannot see each other's plans.
    monkeypatch.setenv("BEP_DATA_DIR", tempfile.mkdtemp(prefix="bep-cli-"))
    from bepkit.cli import cli

    return CliRunner(), cli


def invoke(runner, *args):
    client, cli = runner
    result = client.invoke(cli, list(args), catch_exceptions=False)
    return result


def test_frameworks_lists_the_builtins(runner):
    result = invoke(runner, "frameworks")
    assert result.exit_code == 0
    assert "iso19650" in result.output
    assert "nbims_us" in result.output


def test_create_set_and_score(runner):
    assert invoke(runner, "new", "Bridge 12", "--framework", "lite").exit_code == 0
    assert invoke(runner, "set", "bridge-12", "basics.client", "Region").exit_code == 0

    result = invoke(runner, "score", "bridge-12")
    assert result.exit_code == 0
    assert "/100" in result.output
    assert "Sections" in result.output


def test_score_json_is_machine_readable(runner):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    result = invoke(runner, "score", "bridge-12", "--json")
    report = json.loads(result.output)
    assert report["framework"]["id"] == "lite"
    assert report["score"] >= 0


def test_fail_under_gates_ci(runner):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    result = invoke(runner, "score", "bridge-12", "--fail-under", "90")
    assert result.exit_code == 2


def test_require_ready_gate(runner):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    assert invoke(runner, "score", "bridge-12", "--require-ready").exit_code == 3


def test_demo_scores_well_and_passes_the_gate(runner):
    assert invoke(runner, "demo").exit_code == 0
    result = invoke(runner, "score", "riverside-interchange-phase-2", "--require-ready")
    assert result.exit_code == 0
    assert "READY TO ISSUE" in result.output


def test_set_rejects_an_invalid_option(runner):
    invoke(runner, "new", "Bridge 12", "--framework", "iso19650")
    result = invoke(runner, "set", "bridge-12", "project_information.bep_status", "whenever")
    assert result.exit_code == 1
    assert "not one of" in result.output


def test_export_writes_a_file(runner, tmp_path):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    target = tmp_path / "plan.md"
    result = invoke(runner, "export", "bridge-12", "--format", "md", "--out", str(target))
    assert result.exit_code == 0
    assert target.read_text().startswith("# BIM Execution Plan")


def test_export_import_round_trip(runner, tmp_path):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    invoke(runner, "set", "bridge-12", "basics.client", "Region")
    target = tmp_path / "plan.json"
    invoke(runner, "export", "bridge-12", "--format", "json", "--out", str(target))

    assert invoke(runner, "import", str(target)).exit_code == 0
    listing = invoke(runner, "list").output
    assert listing.count("bridge-12") == 2


def test_korean_labels_in_the_cli(runner):
    result = invoke(runner, "--lang", "ko", "framework", "iso19650")
    assert "프로젝트 정보" in result.output


def test_config_reports_its_sources(runner):
    result = invoke(runner, "config")
    assert "defaults.json" in result.output
    assert "ai.model" in result.output


def test_unknown_project_exits_nonzero(runner):
    result = invoke(runner, "score", "does-not-exist")
    assert result.exit_code == 1
    assert "no project" in result.output


def test_word_export_from_the_cli(runner, tmp_path):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    target = tmp_path / "plan.docx"
    result = invoke(runner, "export", "bridge-12", "--format", "docx", "--out", str(target))
    assert result.exit_code == 0
    assert target.read_bytes()[:2] == b"PK"


def test_word_alias_is_accepted(runner, tmp_path):
    invoke(runner, "new", "Bridge 12", "--framework", "lite")
    target = tmp_path / "plan.docx"
    assert invoke(runner, "export", "bridge-12", "-f", "word", "-o", str(target)).exit_code == 0
    assert target.exists()
