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


def test_known_classes_say_which_schemas_define_them():
    from bepkit.ids import known_classes

    by_name = {c["name"]: c["schemas"] for c in known_classes()}
    assert by_name["IfcWall"] == ["IFC2X3", "IFC4", "IFC4X3_ADD2"]
    assert by_name["IfcCourse"] == ["IFC4X3_ADD2"]
    assert "IfcProduct" not in by_name                      # abstract
    assert [c["name"] for c in known_classes(["IFC2X3"])][:2] == ["IfcAnnotation", "IfcBeam"]


def test_the_class_list_follows_the_settings():
    from bepkit.ids import known_classes
    from bepkit.settings import override

    override("ids.class_root", "IfcWall")
    names = [c["name"] for c in known_classes(["IFC4"])]
    assert names == ["IfcWall", "IfcWallElementedCase", "IfcWallStandardCase"]


WALL_ROW = {"element": "Walls", "ifc_class": "IfcWall", "stage": "3"}
UNICLASS = "https://identifier.buildingsmart.org/uri/nbs/uniclass2015/1"


def test_the_classification_facet_points_at_the_bsdd_dictionary():
    from bepkit.ids import build

    result = build(FakeProject(), _framework(), _values([WALL_ROW]))
    assert (result.classification, result.classification_uri) == ("Uniclass 2015", UNICLASS)
    assert f'uri="{UNICLASS}"' in result.xml

    values = _values([WALL_ROW])
    values["standards_methods"]["classification"] = "OmniClass tables 21 and 23"
    result = build(FakeProject(), _framework(), values)
    assert result.classification == "OmniClass tables 21 and 23" and result.classification_uri == ""
    assert "identifier.buildingsmart.org" not in result.xml


def test_bsdd_names_match_whole_words_offline_and_the_api_only_when_asked(monkeypatch):
    from bepkit.ids import bsdd, classification_uri
    from bepkit.settings import override

    assert classification_uri("NBS Uniclass 2015 (tables Ss, Pr)") == UNICLASS
    assert classification_uri("cci") == bsdd.dictionaries_offline()["CCI"]
    assert classification_uri("") == ""

    calls = []
    monkeypatch.setattr(bsdd, "fetch_dictionaries", lambda *a, **k: calls.append(1) or [
        {"name": "OmniClass", "version": "1", "uri": "https://x/omniclass", "latest": True}])
    assert classification_uri("OmniClass tables 21") == "" and calls == []
    override("ids.bsdd_lookup", True)
    assert classification_uri("OmniClass tables 21") == "https://x/omniclass"

    def offline(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(bsdd, "fetch_dictionaries", offline)
    assert classification_uri("MasterFormat", lookup=True) == ""


def test_property_data_types_follow_the_standard_template_unless_forced():
    from bepkit.ids import build, property_data_type
    from bepkit.settings import override

    assert property_data_type("Pset_WallCommon", "IsExternal", ["IFC2X3"]) == "IFCBOOLEAN"
    assert property_data_type("Pset_WallCommon", "isexternal", ["IFC4X3_ADD2"]) == "IFCBOOLEAN"
    assert property_data_type("Pset_DoorCommon", "FireRating", ["IFC4"]) == "IFCLABEL"
    assert property_data_type("BEP_Requirements", "Grade", ["IFC4"]) is None

    row = dict(WALL_ROW, alphanumeric="Pset_WallCommon.IsExternal, Grade")
    xml = build(FakeProject(), _framework(), _values([row])).xml
    assert 'dataType="IFCBOOLEAN"' in xml and xml.count("dataType=") == 1

    override("ids.data_types", {"grade": "IfcText"})
    assert property_data_type("BEP_Requirements", "Grade", ["IFC4"]) == "IFCTEXT"
    override("ids.data_type", "IFCLABEL")
    assert property_data_type("Pset_WallCommon", "IsExternal", ["IFC2X3"]) == "IFCLABEL"
    assert property_data_type("BEP_Requirements", "Grade", ["IFC4"]) == "IFCTEXT"
