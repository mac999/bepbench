import io
import json

import pytest

from bepkit import services


def test_dashboard_lists_projects(client, project):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test Plan" in response.data


def test_health_check(client):
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_project_home_redirects_to_the_first_section(client, project):
    response = client.get(f"/p/{project.slug}")
    assert response.status_code == 302
    assert "project_information" in response.headers["Location"]


def test_unknown_project_is_a_404_page(client):
    response = client.get("/p/nope/score")
    assert response.status_code == 404
    assert b"does not exist" in response.data


def test_create_project_through_the_form(client):
    response = client.post("/projects", data={"name": "Bridge 12", "framework": "lite",
                                              "client": "Region"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Bridge 12".encode() in response.data


def test_autosave_returns_fresh_scores(client, project):
    response = client.put(
        f"/api/projects/{project.slug}/values",
        json={"values": {"objectives_uses.bim_goals": "Reduce rework " * 50}},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["updated"] == 1
    assert body["score"] > 0
    assert any(s["id"] == "objectives_uses" for s in body["section_detail"])
    assert "recommendations" in body


def test_autosave_rejects_an_invalid_option(client, project):
    response = client.put(
        f"/api/projects/{project.slug}/values",
        json={"values": {"security.security_triage": "Maybe"}},
    )
    assert response.status_code == 400
    assert "not one of" in response.get_json()["error"]


def test_score_api_shape(client, project):
    body = client.get(f"/api/projects/{project.slug}/score").get_json()
    assert set(body) >= {"score", "coverage", "required_coverage", "maturity",
                         "sections", "issues", "recommendations", "ready_to_issue"}
    assert len(body["sections"]) == 16


@pytest.mark.parametrize("fmt, needle", [("md", b"# BIM Execution Plan"),
                                         ("html", b"<!doctype html>"),
                                         ("json", b'"bep_format"')])
def test_exports(client, project, fmt, needle):
    response = client.get(f"/p/{project.slug}/export?format={fmt}")
    assert response.status_code == 200
    assert needle in response.data
    assert "attachment" in response.headers["Content-Disposition"]


def test_export_without_the_assessment(client, project):
    with_score = client.get(f"/p/{project.slug}/export?format=md&score=1").data
    without = client.get(f"/p/{project.slug}/export?format=md&score=0").data
    assert b"Completeness Assessment" in with_score
    assert b"Completeness Assessment" not in without


def test_language_switch_sets_a_cookie_and_translates(client, project):
    response = client.get("/lang/ko", headers={"Referer": "/"})
    assert response.status_code == 302
    assert "bep_lang=ko" in response.headers.get("Set-Cookie", "")

    client.set_cookie("bep_lang", "ko")
    page = client.get(f"/p/{project.slug}/s/project_information")
    assert "프로젝트 정보".encode() in page.data
    assert 'lang="ko"'.encode() in page.data


def test_import_round_trip_through_the_web(client, project):
    payload = json.dumps(services.export_dict(project)).encode()
    response = client.post("/import", data={"file": (io.BytesIO(payload), "plan.json")},
                           content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert len(services.list_projects()) == 2


def test_import_rejects_rubbish(client):
    response = client.post("/import", data={"file": (io.BytesIO(b"not json"), "x.json")},
                           content_type="multipart/form-data", follow_redirects=True)
    assert "not valid BEP JSON".encode() in response.data


def test_delete_requires_the_exact_slug(client, project):
    client.post(f"/p/{project.slug}/delete", data={"confirm": "wrong"}, follow_redirects=True)
    assert len(services.list_projects()) == 1
    client.post(f"/p/{project.slug}/delete", data={"confirm": project.slug}, follow_redirects=True)
    assert services.list_projects() == []


def test_viewer_settings_are_served_to_the_client(client):
    body = client.get("/api/settings/viewer").get_json()
    assert "modes" in body and "lod" in body and "palette" in body
    assert body["lod"]["levels"]["100"]["geometry"] == "bbox"


def test_ai_status_is_reported_without_crashing(client):
    body = client.get("/api/ai/status").get_json()
    assert "enabled" in body and "reachable" in body


def test_assist_rejects_an_unknown_field(client, project):
    response = client.post(f"/api/projects/{project.slug}/assist",
                           json={"path": "nope.nothing"})
    assert response.status_code == 404


def test_editor_page_carries_the_lod_binding(client, project):
    page = client.get(f"/p/{project.slug}/s/information_requirements").data.decode()
    assert 'data-lod-field="information_requirements.loin"' in page
    assert 'data-lod-column="lod"' in page
    # and an ordinary section does not claim to drive the viewer
    other = client.get(f"/p/{project.slug}/s/risk").data.decode()
    assert 'data-lod-field=""' in other


def test_word_export_is_a_real_docx(client, project):
    response = client.get(f"/p/{project.slug}/export?format=docx")
    assert response.status_code == 200
    assert response.data[:2] == b"PK"                       # a zip container
    assert "wordprocessingml" in response.headers["Content-Type"]
    assert response.headers["Content-Disposition"].endswith('.docx"')


def test_word_export_carries_no_tool_fingerprints(client, project):
    import io
    import zipfile

    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/p/{project.slug}/export?format=docx").data))
    assert "docProps/thumbnail.jpeg" not in archive.namelist()
    app_xml = archive.read("docProps/app.xml").decode()
    assert "<Application></Application>" in app_xml
    assert "Microsoft" not in app_xml
    core = archive.read("docProps/core.xml").decode()
    assert "2013" not in core                               # the template's own date
    assert project.client in app_xml


def test_menu_bar_offers_word_and_the_assessment(client, project):
    page = client.get(f"/p/{project.slug}/s/project_information").data.decode()
    assert "Save as Word" in page
    assert "Completeness assessment" in page
    assert f"/p/{project.slug}/export?format=docx" in page.replace("&amp;", "&")


def test_properties_pane_includes_the_object_tree(client, project):
    page = client.get(f"/p/{project.slug}/s/project_information").data.decode()
    assert "data-tree" in page
    assert "data-tree-filter" in page
    assert 'data-tab="properties"' in page


def test_ids_export_serves_a_valid_document(client, project):
    from bepkit.cli.demo_data import DEMO_VALUES

    services.set_values(project, {
        "information_requirements.loin": DEMO_VALUES["information_requirements.loin"],
        "standards_methods.classification": "Uniclass 2015",
    })
    response = client.get(f"/api/projects/{project.slug}/ids")
    assert response.status_code == 200
    assert b"<ids" in response.data
    assert "xml" in response.headers["Content-Type"]
    assert response.headers["Content-Disposition"].endswith('.ids"')


def test_ids_export_explains_an_empty_table(client, project):
    response = client.get(f"/api/projects/{project.slug}/ids")
    assert response.status_code == 422
    assert "empty" in response.get_json()["error"]


def test_stage_is_chosen_at_creation_and_shown_on_the_score(client):
    client.post("/projects", data={"name": "Tender plan", "framework": "iso19650",
                                   "stage": "pre_appointment"}, follow_redirects=True)
    created = services.list_projects()[0]
    assert created.stage == "pre_appointment"

    page = client.get(f"/p/{created.slug}/score").data.decode()
    assert "Pre-appointment" in page


def test_diff_needs_a_snapshot_first(client, project):
    response = client.get(f"/p/{project.slug}/diff", follow_redirects=True)
    assert "Take a snapshot first" in response.data.decode()

    assert client.get(f"/api/projects/{project.slug}/diff").status_code == 422


def test_diff_page_reports_what_moved(client, project):
    services.set_value(project, "objectives_uses", "bim_goals", "word " * 90)
    services.take_snapshot(project, "P01")
    services.set_value(project, "risk", "risk_process", "Reviewed fortnightly.")

    page = client.get(f"/p/{project.slug}/diff").data.decode()
    assert "Risk Review Process" in page
    assert "P01" in page

    body = client.get(f"/api/projects/{project.slug}/diff").get_json()
    assert body["counts"]["added"] == 1
    assert body["score_delta"] > 0
