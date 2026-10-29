"""A new plan from an empty database, through every feature, as a user meets them.

Each step is what the web app or the API does after the one before it, so a
break anywhere in the chain fails here even when each unit still passes alone.
Malformed input must come back as a 4xx with a message, never as a 500.
"""

import base64
import io
import json
from pathlib import Path

import pytest

from bepkit.ids import IFCTESTER_AVAILABLE

DUPLEX = Path(__file__).resolve().parent.parent / "docs" / "demo" / "Duplex_A.ifc"
needs_ifc = pytest.mark.skipif(not IFCTESTER_AVAILABLE, reason="ifctester not installed")

LOIN = [
    {"element": "Walls", "ifc_class": "IfcWall", "lod": "300", "stage": "3",
     "alphanumeric": "Pset_WallCommon.IsExternal"},
    {"element": "Doors", "lod": "300", "stage": "3", "alphanumeric": "Pset_DoorCommon.FireRating"},
    {"element": "Lifts", "lod": "300", "stage": "4"},
]


def _upload(client, slug, path=DUPLEX, name=None):
    with open(path, "rb") as handle:
        return client.post(f"/api/projects/{slug}/models",
                           data={"file": (handle, name or path.name)})


def test_a_plan_built_from_scratch_works_end_to_end(client):
    # Create from the dashboard form, then land on the first section.
    response = client.post("/projects", data={"name": "Flow Tower", "framework": "iso19650",
                                              "client": "Acme", "reference": "FT-1"})
    assert response.status_code == 302
    slug = "flow-tower"
    assert client.get(f"/p/{slug}", follow_redirects=True).status_code == 200

    # Every section of the framework opens, empty as it is.
    framework = client.get("/api/frameworks/iso19650").get_json()
    for section in framework["sections"]:
        assert client.get(f"/p/{slug}/s/{section['id']}").status_code == 200, section["id"]

    # Autosave a few answers and get a fresh score back.
    saved = client.put(f"/api/projects/{slug}/values", json={
        "project_information.project_description": "Twelve storeys — 한글 포함",
        "project_information.project_stage": "3 Spatial Coordination",
        "information_requirements.loin": LOIN,
    })
    assert saved.status_code == 200 and saved.get_json()["updated"] == 3
    assert saved.get_json()["score"] > 0

    for page in ("score", "preview", "document", "settings"):
        assert client.get(f"/p/{slug}/{page}").status_code == 200, page
    for fmt in ("md", "html", "json", "docx"):
        assert client.get(f"/p/{slug}/export?format={fmt}").status_code == 200, fmt

    # Versions: snapshot, change, compare, restore.
    assert client.post(f"/api/projects/{slug}/snapshots", json={"label": "v1"}).status_code == 201
    client.put(f"/api/projects/{slug}/values", json={"project_information.project_name": "Flow B"})
    diff = client.get(f"/api/projects/{slug}/diff").get_json()
    assert any(c["path"] == "project_information.project_name"
               for s in diff["sections"] for c in s["changes"])
    assert client.get(f"/p/{slug}/diff").status_code == 200
    snapshot = client.get(f"/api/projects/{slug}/snapshots").get_json()[0]
    client.post(f"/p/{slug}/snapshots/{snapshot['id']}/restore")
    assert (client.get(f"/api/projects/{slug}").get_json()["values"]["project_information"]
            ["project_name"] == "Flow Tower")

    # Korean reads the same plan.
    client.set_cookie("bep_lang", "ko")
    assert client.get(f"/p/{slug}/s/project_information").status_code == 200
    client.set_cookie("bep_lang", "en")

    # Copy, then delete the original with its confirmation.
    assert client.post(f"/p/{slug}/duplicate").status_code == 302
    assert client.post(f"/p/{slug}/delete", data={"confirm": slug}).status_code == 302
    slugs = [p["slug"] for p in client.get("/api/projects").get_json()]
    assert slug not in slugs and len(slugs) == 1


@needs_ifc
def test_a_new_plan_checks_its_models_against_its_own_requirements(client):
    client.post("/api/projects", json={"name": "Checked", "framework": "iso19650"})
    client.put("/api/projects/checked/values", json={"information_requirements.loin": LOIN})

    model = _upload(client, "checked")
    assert model.status_code == 201
    model_id = model.get_json()["id"]
    assert client.get(f"/api/projects/checked/models/{model_id}/index").status_code == 200
    assert client.get(f"/api/projects/checked/models/{model_id}/buffer").status_code == 200

    milestones = client.get("/api/projects/checked/ids/milestones").get_json()
    assert milestones["milestones"] == ["3", "4"]
    assert client.get("/api/projects/checked/ids?milestone=3").status_code == 200

    report = client.post("/api/projects/checked/ids/check", json={}).get_json()
    by_name = {r["name"]: r for r in report["results"]}
    assert by_name["Walls"]["applicable"] > 1          # IfcWallStandardCase counted too
    assert by_name["Lifts"]["status"] == "not_applicable"

    assert client.delete(f"/api/projects/checked/models/{model_id}").status_code == 200
    assert client.get("/api/projects/checked/models").get_json() == []


@pytest.mark.parametrize("method,path", [
    ("post", "/api/projects"),
    ("put", "/api/projects/{slug}/values"),
    ("patch", "/api/projects/{slug}"),
    ("post", "/api/projects/{slug}/snapshots"),
    ("post", "/api/projects/{slug}/assist"),
    ("post", "/api/projects/{slug}/ids/check"),
    ("post", "/api/import"),
])
def test_a_json_body_that_is_not_an_object_is_a_400(client, project, method, path):
    response = getattr(client, method)(path.format(slug=project.slug), json=[1, 2])
    assert response.status_code == 400
    assert response.get_json()["error"] == "send a JSON object"


def test_null_text_fields_on_create_are_treated_as_empty(client):
    response = client.post("/api/projects", json={"name": "Nulls", "framework": "lite",
                                                  "client": None, "reference": None})
    assert response.status_code == 201
    assert response.get_json()["client"] == ""


@pytest.mark.parametrize("payload", [
    {"framework": "lite", "values": [1]},
    {"framework": "lite", "values": {"basics": [1]}},
    {"project": "x", "framework": "lite"},
])
def test_a_malformed_import_is_refused_with_a_message(client, payload):
    response = client.post("/api/import", json=payload)
    assert response.status_code == 400
    assert "object" in response.get_json()["error"]


def test_a_web_import_of_a_json_list_is_refused_not_a_crash(client):
    response = client.post("/import", data={"file": (io.BytesIO(b"[1]"), "plan.json")})
    assert response.status_code == 302


def test_a_bad_value_leaves_its_whole_batch_unapplied(client, project):
    response = client.put(f"/api/projects/{project.slug}/values", json={
        "project_information.project_name": "Changed",
        "project_information.project_stage": "not a stage",
    })
    assert response.status_code == 400
    values = client.get(f"/api/projects/{project.slug}").get_json()["values"]
    assert values["project_information"]["project_name"] == "Test Plan"


def test_settings_refuse_a_blank_name_and_an_unknown_stage(client, project):
    for form in ({"name": ""}, {"name": "Kept", "stage": "zzz"}):
        response = client.post(f"/p/{project.slug}/settings", data=form)
        assert response.status_code == 302
    assert client.get(f"/api/projects/{project.slug}").get_json()["project"]["name"] == "Test Plan"
    assert client.patch(f"/api/projects/{project.slug}", json={"name": " "}).status_code == 400


def test_the_api_returns_word_as_base64(client, project):
    body = client.get(f"/api/projects/{project.slug}/export?format=docx").get_json()
    assert body["encoding"] == "base64"
    assert base64.b64decode(body["content"])[:2] == b"PK"


@needs_ifc
def test_a_rejected_upload_leaves_no_model_behind(client, project):
    response = client.post(f"/api/projects/{project.slug}/models",
                           data={"file": (io.BytesIO(b"not an ifc"), "broken.ifc")})
    assert response.status_code == 400
    assert client.get(f"/api/projects/{project.slug}/models").get_json() == []


@needs_ifc
def test_a_model_without_viewer_data_is_a_404_not_a_crash(client, project):
    from bepkit import services
    from bepkit.extensions import db

    model_id = _upload(client, project.slug).get_json()["id"]
    model = services.get_model(project, model_id)
    model.status = "failed"
    db.session.commit()
    for part in ("index", "buffer"):
        assert client.get(f"/api/projects/{project.slug}/models/{model_id}/{part}").status_code == 404


def test_a_model_id_that_is_not_a_number_is_a_422(client, project):
    response = client.post(f"/api/projects/{project.slug}/ids/check", json={"model_ids": ["abc"]})
    assert response.status_code == 422


@pytest.mark.parametrize("element,expected", [
    ("Windows", "IfcWindow"),
    ("External doors", "IfcDoor"),
    ("Lifts", "IfcTransportElement"),
    ("Curtain walls", "IfcCurtainWall"),
    ("Glass", None),
])
def test_class_inference_reads_plural_element_names(element, expected):
    from bepkit.ids.builder import infer_ifc_class

    assert infer_ifc_class(element) == expected


@needs_ifc
def test_a_requirement_covers_the_subtypes_every_target_schema_defines():
    from bepkit.ids.builder import concrete_subtypes

    assert concrete_subtypes("IfcWall", ["IFC2X3"]) == ["IFCWALLSTANDARDCASE"]
    assert "IFCWALLELEMENTEDCASE" in concrete_subtypes("IfcWall", ["IFC4"])
    assert concrete_subtypes("IfcWall", ["IFC2X3", "IFC4"]) == ["IFCWALLSTANDARDCASE"]
    assert concrete_subtypes("IfcDoor", ["IFC2X3"]) == []


@needs_ifc
def test_subtype_matching_follows_the_setting(app, project):
    from bepkit import services
    from bepkit.settings import override

    services.set_values(project, {"information_requirements.loin": LOIN[:1]})
    with open(DUPLEX, "rb") as handle:
        services.attach_model(project, handle, "Duplex_A.ifc")

    walls = services.check_ids(project)["results"][0]
    override("ids.include_subtypes", False)
    exact = services.check_ids(project)["results"][0]
    assert walls["applicable"] > exact["applicable"] == 1


def test_the_editor_offers_the_viewer_retry_strings(client, project):
    page = client.get(f"/p/{project.slug}/s/project_information").get_data(as_text=True)
    strings = json.loads(page.split("data-strings='", 1)[1].split("'", 1)[0]) \
        if "data-strings='" in page else None
    assert strings is None or {"viewer_missing", "viewer_upload_failed"} <= set(strings)
    assert "viewer_missing" in page


def test_the_hidden_attribute_wins_over_component_display(client):
    # .viewer-overlay sets display: grid; without this rule its spinner never hid.
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert "[hidden] { display: none !important; }" in css
