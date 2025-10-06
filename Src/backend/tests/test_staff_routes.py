from __future__ import annotations

from typing import Dict

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, username: str = "po_admin") -> Dict[str, str]:
    response = client.post(f"/auth/token?username={username}&password=x")
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_staff_recommend_accepts_project_key(client: TestClient) -> None:
    headers = _auth_headers(client)

    projects_resp = client.get("/projects", headers=headers)
    assert projects_resp.status_code == 200
    projects = projects_resp.json()
    assert projects, "Expected seeded projects"
    project_px = next((project for project in projects if project["key"] == "PX"), None)
    assert project_px is not None, "PX project should be seeded"

    resp_by_key = client.get("/staff/recommend", headers=headers, params={"project_key": "PX"})
    assert resp_by_key.status_code == 200
    data_by_key = resp_by_key.json()
    assert data_by_key["project_id"] == project_px["id"]
    assert data_by_key["candidates"], "Expected at least one candidate"
    for candidate in data_by_key["candidates"]:
        assert "skill_gaps" in candidate
        assert isinstance(candidate["skill_gaps"], list)
        if candidate["skill_gaps"]:
            sample_gap = candidate["skill_gaps"][0]
            assert {"name", "path", "gap"}.issubset(sample_gap.keys())

    resp_by_id = client.get(
        "/staff/recommend",
        headers=headers,
        params={"project_id": project_px["id"]},
    )
    assert resp_by_id.status_code == 200
    assert resp_by_id.json()["candidates"] == data_by_key["candidates"]


def test_staff_recommend_requires_identifier(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/staff/recommend", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Provide project_id or project_key"


def test_staff_recommend_unknown_project_key(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get(
        "/staff/recommend",
        headers=headers,
        params={"project_key": "does-not-exist"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
