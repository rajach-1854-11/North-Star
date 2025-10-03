from __future__ import annotations

from fastapi.testclient import TestClient


def _get_token(client: TestClient, username: str) -> str:
    response = client.post(f"/auth/token?username={username}&password=x")
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_retrieve_rejects_unknown_project(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_get_token(client, 'dev_alex')}"}
    response = client.post(
        "/retrieve",
        headers=headers,
        json={"query": "status", "targets": ["NON_EXISTENT"], "k": 3},
    )
    assert response.status_code == 403


def test_authorization_header_required(client: TestClient) -> None:
    response = client.get("/projects?token=fake")
    assert response.status_code == 401