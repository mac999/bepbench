"""Appointment stages: a tender BEP is not a half-written delivery BEP."""

import pytest

from bepkit import services
from bepkit.schema import get_framework
from bepkit.scoring import evaluate


def test_framework_splits_into_two_honest_stages():
    framework = get_framework("iso19650")
    total = framework.total_fields
    pre = framework.fields_in_stage("pre_appointment")
    delivery = framework.fields_in_stage("delivery")

    assert pre < total, "no field is marked delivery-only, so the stages do nothing"
    assert delivery == total, "the delivery stage must ask for the whole plan"
    assert pre > total * 0.5, "a tender BEP still answers most of the plan"


def test_unknown_stage_in_a_framework_is_a_load_error():
    from bepkit.schema.models import Field

    with pytest.raises(ValueError, match="unknown stage"):
        Field.from_dict({"id": "x", "stages": ["halfway"]})


def test_same_answers_score_higher_as_a_tender_than_as_a_delivery_plan(app):
    from bepkit.cli.demo_data import DEMO_VALUES

    framework = get_framework("iso19650")
    values: dict = {}
    for path in (f"{s.id}.{f.id}" for s, f in framework.iter_fields("pre_appointment")):
        if path in DEMO_VALUES:
            section, field_id = path.split(".", 1)
            values.setdefault(section, {})[field_id] = DEMO_VALUES[path]

    pre = evaluate(framework, values, stage="pre_appointment")
    delivery = evaluate(framework, values, stage="delivery")

    assert pre.score > delivery.score + 10
    assert pre.fields_total < delivery.fields_total
    assert pre.stage == "pre_appointment"


def test_delivery_only_fields_raise_no_issues_at_tender_stage(app):
    framework = get_framework("iso19650")
    pre = evaluate(framework, {}, stage="pre_appointment")
    delivery = evaluate(framework, {}, stage="delivery")

    pre_paths = {i.id for i in pre.issues}
    assert "required:delivery_strategy.midp_approach" not in pre_paths
    assert "required:delivery_strategy.midp_approach" in {i.id for i in delivery.issues}


def test_project_remembers_its_stage_and_scores_by_it(app):
    project = services.create_project("Tender", "iso19650", stage="pre_appointment")
    assert project.stage == "pre_appointment"
    assert services.score_project(project).stage == "pre_appointment"
    # and can be asked about the other stage without changing the record
    assert services.score_project(project, "delivery").stage == "delivery"
    assert project.stage == "pre_appointment"


def test_unknown_stage_is_refused(app):
    with pytest.raises(services.ServiceError, match="unknown stage"):
        services.create_project("Nope", "iso19650", stage="whenever")

    project = services.create_project("Fine", "iso19650")
    with pytest.raises(services.ServiceError, match="unknown stage"):
        services.update_project(project, stage="sometime")
