"""IDS export. Skipped when ifctester is absent, since it is optional."""

import pytest

from bepkit.ids import IFCTESTER_AVAILABLE, IdsError, infer_ifc_class, split_properties

pytestmark = pytest.mark.skipif(not IFCTESTER_AVAILABLE, reason="ifctester not installed")


class FakeProject:
    name = "Riverside"
    client = "City Transport Authority"
    reference = "RIV-2026-002"
    owner = "J. Salim"


def _framework():
    from bepkit.schema import get_framework

    return get_framework("iso19650")


def _values(rows):
    return {"information_requirements": {"loin": rows},
            "standards_methods": {"classification": "Uniclass 2015 — tables Ss, Pr"}}


def test_inference_prefers_the_longest_matching_hint():
    assert infer_ifc_class("Curtain wall panel") == "IfcCurtainWall"
    assert infer_ifc_class("External wall") == "IfcWall"
    assert infer_ifc_class("Viaduct deck") == "IfcSlab"
    assert infer_ifc_class("Something unnameable") is None


def test_properties_are_split_on_ordinary_punctuation():
    got = split_properties("Grade, mass; fire rating and install sequence ID")
    assert got == ["Grade", "mass", "fire rating", "install sequence ID"]
    assert split_properties("") == []


def test_declared_class_wins_over_inference():
    from bepkit.ids import build

    rows = [{"element": "Deck", "ifc_class": "IfcBeam", "lod": "400",
             "stage": "4", "geometry": "g", "alphanumeric": "Grade"}]
    result = build(FakeProject(), _framework(), _values(rows))
    assert "IFCBEAM" in result.xml
    assert not result.inferred            # nothing was guessed


def test_rows_without_a_resolvable_class_are_reported_not_guessed():
    from bepkit.ids import build

    rows = [
        {"element": "Wall type A", "lod": "300", "alphanumeric": "Fire rating"},
        {"element": "Zzz unnameable thing", "lod": "300", "alphanumeric": "x"},
    ]
    result = build(FakeProject(), _framework(), _values(rows))
    assert result.specifications == 1
    assert len(result.skipped) == 1
    assert "Zzz" in result.skipped[0].element


def test_generated_document_is_schema_valid(tmp_path):
    from ifctester import ids as ids_model

    from bepkit.ids import build

    rows = [{"element": "External wall", "ifc_class": "IfcWall", "lod": "350",
             "stage": "4", "geometry": "Cavity build-up",
             "alphanumeric": "Fire rating, U-value, acoustic rating"}]
    result = build(FakeProject(), _framework(), _values(rows))

    path = tmp_path / "plan.ids"
    path.write_text(result.xml, encoding="utf-8")
    document = ids_model.open(str(path), validate=True)      # raises if invalid

    assert len(document.specifications) == 1
    spec = document.specifications[0]
    assert spec.name == "External wall"
    # the floor of any LOIN: a named, classified element carrying its properties
    kinds = {type(r).__name__ for r in spec.requirements}
    assert {"Attribute", "Classification", "Property"} <= kinds


def test_author_is_always_an_email_as_ids_requires():
    from bepkit.ids import build

    rows = [{"element": "Wall", "ifc_class": "IfcWall", "alphanumeric": "Grade"}]
    xml = build(FakeProject(), _framework(), _values(rows)).xml
    assert "j.salim@example.com" in xml


def test_empty_table_is_refused_with_an_explanation():
    from bepkit.ids import build

    with pytest.raises(IdsError, match="empty"):
        build(FakeProject(), _framework(), _values([]))


def test_every_framework_with_a_loin_table_is_mapped():
    from bepkit.ids import loin_source
    from bepkit.schema import get_framework

    for framework_id in ("iso19650", "nbims_us"):
        source = loin_source(framework_id)
        framework = get_framework(framework_id)
        section = framework.section_by_id(source["section"])
        assert section is not None, framework_id
        field = section.field_by_id(source["field"])
        assert field is not None and field.type == "table", framework_id
        columns = {c.id for c in field.columns}
        for role, column in source.get("columns", {}).items():
            assert column in columns, f"{framework_id}: {role} -> {column}"
