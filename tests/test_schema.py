import pytest

from bepkit.schema import available_frameworks, get_framework
from bepkit.schema.locale import localize


def test_every_builtin_framework_loads_and_validates():
    frameworks = available_frameworks()
    assert {f.id for f in frameworks} >= {"iso19650", "nbims_us", "lite"}
    for framework in frameworks:
        framework.validate()
        assert framework.sections, f"{framework.id} has no sections"
        assert framework.total_fields > 0


def test_field_paths_are_unique_and_resolvable():
    framework = get_framework("iso19650")
    paths = [f"{s.id}.{f.id}" for s, f in framework.iter_fields()]
    assert len(paths) == len(set(paths))
    for path in paths:
        assert framework.resolve(path) is not None


def test_checks_reference_existing_fields():
    for framework in available_frameworks():
        for check in framework.checks:
            section = framework.section_by_id(check.section)
            assert section is not None, f"{framework.id}:{check.id}"
            field_id = check.params.get("field")
            if field_id:
                assert section.field_by_id(field_id) is not None, f"{framework.id}:{check.id}"


def test_unknown_framework_raises():
    with pytest.raises(KeyError):
        get_framework("does-not-exist")


def test_korean_overlay_translates_display_only():
    english = get_framework("iso19650")
    korean = localize(english, "ko")

    assert korean.sections[0].title != english.sections[0].title
    # ids, types and option values must survive translation untouched
    assert [s.id for s in korean.sections] == [s.id for s in english.sections]
    for (sec_en, f_en), (sec_ko, f_ko) in zip(english.iter_fields(), korean.iter_fields()):
        assert f_en.id == f_ko.id
        assert f_en.type == f_ko.type
        assert f_en.options == f_ko.options
        assert f_en.required == f_ko.required


def test_missing_translation_falls_back_to_english():
    framework = localize(get_framework("nbims_us"), "ko")
    assert framework.sections[0].title == get_framework("nbims_us").sections[0].title


def test_documented_framework_sizes_match_the_yaml():
    """The README quotes concrete counts; they must not drift from the files."""
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    framework = get_framework("iso19650")

    quoted = re.search(r"ISO 19650-2 \((\d+) sections, (\d+) fields\)", readme)
    assert quoted, "README no longer states the ISO framework size"
    assert int(quoted.group(1)) == len(framework.sections)
    assert int(quoted.group(2)) == framework.total_fields

    delivery_only = framework.total_fields - framework.fields_in_stage("pre_appointment")
    stated = re.search(r"(\d+) of (\d+) fields are marked delivery-only", readme)
    assert stated, "README no longer states the delivery-only count"
    assert int(stated.group(1)) == delivery_only
    assert int(stated.group(2)) == framework.total_fields
