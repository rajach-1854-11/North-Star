from __future__ import annotations

import time

import jwt
from fastapi.testclient import TestClient

from app.config import settings


def _get_token(client: TestClient, username: str) -> str:
    response = client.post(f"/auth/token?username={username}&password=x")
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _forge_token(**overrides: object) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": overrides.get("sub", "spoof"),
        "user_id": overrides.get("user_id", -1),
        "role": overrides.get("role", "Admin"),
        "tenant_id": overrides.get("tenant_id", settings.tenant_id),
        "accessible_projects": overrides.get("accessible_projects", ["global"]),
        "iss": settings.jwt_iss,
        "aud": settings.jwt_aud,
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token


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


def test_retrieve_unknown_tenant_returns_404(client: TestClient) -> None:
    token = _forge_token(tenant_id="ghost", accessible_projects=["PX", "global"])
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/retrieve",
        headers=headers,
        json={"query": "status", "targets": ["PX"], "k": 3},
    )
    assert response.status_code == 404