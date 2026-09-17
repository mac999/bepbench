"""AI prompt construction and answer parsing — no model is called."""

import pytest

from bepkit.ai import build_prompt, parse_rows
from bepkit.ai.provider import clean
from bepkit.schema import get_framework

FW = get_framework("iso19650")


class FakeProject:
    name = "Riverside Interchange"
    client = "City Transport Authority"
    reference = "RIV-2026-002"


def test_prompt_carries_framework_and_project_context():
    section = FW.section_by_id("cde_workflow")
    field = section.field_by_id("naming_convention")
    values = {"project_information": {"project_name": "Riverside Interchange"},
              "cde_workflow": {"cde_platform": "Autodesk Construction Cloud"}}

    prompt = build_prompt(FakeProject(), FW, section, field, values=values)

    assert "Riverside Interchange" in prompt
    assert "City Transport Authority" in prompt
    assert section.title in prompt
    assert field.label in prompt
    # the depth the scorer will demand is stated to the model
    assert f"{field.quality.min_words} words" in prompt
    # and the rest of the plan is offered as context to stay consistent with
    assert "Autodesk Construction Cloud" in prompt


def test_table_prompt_names_every_column_and_its_options():
    section = FW.section_by_id("objectives_uses")
    field = section.field_by_id("bim_uses")
    prompt = build_prompt(FakeProject(), FW, section, field)

    for column in field.columns:
        assert f'"{column.id}"' in prompt
    assert "JSON array" in prompt
    assert "Core" in prompt  # the priority column's options


def test_korean_prompt_asks_for_korean():
    section = FW.section_by_id("risk")
    prompt = build_prompt(FakeProject(), FW, section, section.field_by_id("risk_process"),
                          language="ko")
    assert "Korean" in prompt


def test_parse_rows_maps_labels_and_ignores_prose_around_the_json():
    field = FW.resolve("approval.appendices")[1]
    answer = (
        "Here are the appendices you need:\n"
        '[{"Ref": "A", "title": "Clash matrix", "location": "CDE"},\n'
        ' {"ref": "B", "title": "MIDP", "location": "CDE"}]\n'
        "Let me know if you want more."
    )
    rows = parse_rows(answer, field)
    assert len(rows) == 2
    assert rows[0]["ref"] == "A"            # matched by label, not key
    assert rows[1]["title"] == "MIDP"
    assert set(rows[0]) == {c.id for c in field.columns}


def test_parse_rows_returns_none_when_there_is_no_table():
    field = FW.resolve("approval.appendices")[1]
    assert parse_rows("I could not produce a table.", field) is None


@pytest.mark.parametrize("raw, expected", [
    ("<think>hmm</think>The answer.", "The answer."),
    ("```markdown\nThe answer.\n```", "The answer."),
    ("  spaced  ", "spaced"),
])
def test_clean_strips_model_wrappers(raw, expected):
    assert clean(raw) == expected


def test_unknown_mode_is_rejected():
    from bepkit.ai import AIError, suggest

    section = FW.section_by_id("risk")
    with pytest.raises(AIError):
        suggest(FakeProject(), FW, section, section.field_by_id("risk_process"), mode="nonsense")
