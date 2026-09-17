"""IFC import. Skipped when ifcopenshell is not installed, since it is optional."""

import pytest

from bepkit.ifcio import ifcopenshell_available

pytestmark = pytest.mark.skipif(not ifcopenshell_available(), reason="ifcopenshell not installed")


@pytest.fixture(scope="module")
def sample_ifc(tmp_path_factory):
    """A tiny two-storey model: enough classes to exercise the LOD filter."""
    import ifcopenshell
    import ifcopenshell.util.placement
    from ifcopenshell.api import run

    path = tmp_path_factory.mktemp("ifc") / "sample.ifc"
    f = run("project.create_file", version="IFC4")
    project = run("root.create_entity", f, ifc_class="IfcProject", name="Test")
    run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})
    ctx = run("context.add_context", f, context_type="Model")
    body = run("context.add_context", f, context_type="Model", context_identifier="Body",
               target_view="MODEL_VIEW", parent=ctx)
    site = run("root.create_entity", f, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", f, ifc_class="IfcBuilding", name="Building")
    run("aggregate.assign_object", f, products=[site], relating_object=project)
    run("aggregate.assign_object", f, products=[building], relating_object=site)
    storey = run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Ground Floor")
    run("aggregate.assign_object", f, products=[storey], relating_object=building)

    for ifc_class, name, x, length, thickness, height in [
        ("IfcWall", "Wall A", 0.0, 6.0, 0.3, 3.0),
        ("IfcSlab", "Slab", 0.0, 6.0, 5.0, 0.2),
        ("IfcFurnishingElement", "Desk", 2.0, 1.6, 0.8, 0.75),
    ]:
        entity = run("root.create_entity", f, ifc_class=ifc_class, name=name)
        run("spatial.assign_container", f, products=[entity], relating_structure=storey)
        rep = run("geometry.add_wall_representation", f, context=body,
                  length=length, height=height, thickness=thickness)
        run("geometry.assign_representation", f, product=entity, representation=rep)
        matrix = ifcopenshell.util.placement.a2p((x, 0.0, 0.0), (0., 0., 1.), (1., 0., 0.))
        run("geometry.edit_object_placement", f, product=entity, matrix=matrix, is_si=True)

    f.write(str(path))
    return path


def test_inspect_reports_schema_and_classes(sample_ifc):
    from bepkit.ifcio import inspect_file

    info = inspect_file(sample_ifc)
    assert info["schema"] == "IFC4"
    assert info["classes"]["IfcWall"] == 1
    assert "Ground Floor" in info["storeys"]


def test_tessellate_writes_a_consistent_payload(sample_ifc, tmp_path):
    from bepkit.ifcio import tessellate

    binary, index_path = tmp_path / "model.bin", tmp_path / "model.json"
    index = tessellate(sample_ifc, binary, index_path)

    assert index["element_count"] == 3
    assert binary.stat().st_size == index["buffer_bytes"]
    assert len(index["bbox"]) == 6

    # every element must address a real slice of the buffer
    for element in index["elements"]:
        assert element["po"] + element["v"] * 12 <= index["buffer_bytes"]
        assert element["io"] + element["t"] * 4 <= index["buffer_bytes"]
        assert element["po"] % 4 == 0 and element["io"] % 4 == 0   # typed-array alignment
        assert element["c"].startswith("Ifc")
        assert element["s"] == "Ground Floor"


def test_element_cap_truncates_rather_than_failing(sample_ifc, tmp_path):
    from bepkit.ifcio import tessellate

    index = tessellate(sample_ifc, tmp_path / "m.bin", tmp_path / "m.json", max_elements=1)
    assert index["element_count"] == 1
    assert index["truncated"] is True


def test_element_properties_reads_back_by_guid(sample_ifc, tmp_path):
    from bepkit.ifcio import element_properties, tessellate

    index = tessellate(sample_ifc, tmp_path / "m.bin", tmp_path / "m.json")
    guid = index["elements"][0]["g"]
    props = element_properties(sample_ifc, guid)
    assert props["guid"] == guid
    assert props["ifc_class"].startswith("Ifc")
    assert props["container"] == "Ground Floor"


def test_unknown_guid_is_reported(sample_ifc):
    from bepkit.ifcio import IfcError, element_properties

    with pytest.raises(IfcError):
        element_properties(sample_ifc, "0000000000000000000000")


def test_lod_config_covers_every_class_the_sample_uses(sample_ifc, tmp_path):
    """The shipped LOD rules must not silently hide ordinary building elements."""
    from bepkit.ifcio import tessellate
    from bepkit.settings import get as setting

    index = tessellate(sample_ifc, tmp_path / "m.bin", tmp_path / "m.json")
    levels = setting("viewer.lod.levels")
    top = levels["500"]
    for ifc_class in index["classes"]:
        assert "*" in top["include"] or ifc_class in top["include"], ifc_class
    # and LOD 100 must be a genuine subset, or the filter is pointless
    assert "*" not in levels["100"]["include"]
    assert levels["100"]["geometry"] == "bbox"


def test_openings_are_never_written_to_the_payload(tmp_path):
    """A void is not an object: no viewer draws it, and it inflates the payload."""
    from bepkit.settings import get as setting

    skip = setting("viewer.skip_classes", [])
    assert "IfcOpeningElement" in skip

    levels = setting("viewer.lod.levels")
    for level, spec in levels.items():
        include = spec.get("include", [])
        exclude = spec.get("exclude", [])
        assert "IfcOpeningElement" not in include, level
        # Room volumes would hide the building; they are off unless asked for.
        assert "IfcSpace" not in include, level
        if "*" in include:
            assert "IfcSpace" in exclude, level
