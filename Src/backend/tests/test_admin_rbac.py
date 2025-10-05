from __future__ import annotations

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.domain import models as m
import app.deps as deps


def _get_token(client: TestClient, username: str) -> str:
    response = client.post(f"/auth/token?username={username}&password=x")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


def _decode_claims(token: str) -> dict:
    decode_kwargs: dict[str, object] = {
        "key": settings.jwt_secret,
        "algorithms": ["HS256"],
        "options": {"verify_signature": True, "verify_exp": False},
    }
    if settings.jwt_aud:
        decode_kwargs["audience"] = settings.jwt_aud
    return jwt.decode(token, **decode_kwargs)


def test_admin_can_list_and_update_roles(client: TestClient) -> None:
    admin_token = _get_token(client, "admin_root")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    listing = client.get("/admin/users", headers=admin_headers)
    assert listing.status_code == 200, listing.text
    users = listing.json()["users"]
    dev = next(user for user in users if user["username"] == "dev_alex")

    response = client.patch(
        f"/admin/users/{dev['id']}/role",
        headers=admin_headers,
        json={"role": "PO"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "PO"

    refreshed = client.get("/admin/users", headers=admin_headers)
    assert refreshed.status_code == 200
    updated_dev = next(user for user in refreshed.json()["users"] if user["username"] == "dev_alex")
    assert updated_dev["role"] == "PO"


def test_assignment_flow_updates_access_and_rbac(client: TestClient) -> None:
    po_token = _get_token(client, "po_admin")
    po_headers = {"Authorization": f"Bearer {po_token}"}

    with deps.SessionLocal() as session:
        developer = (
            session.query(m.Developer)
            .join(m.User, m.User.id == m.Developer.user_id)
            .filter(m.User.username == "dev_alex")
            .one()
        )
        px_project = session.query(m.Project).filter(m.Project.key == "PX").one()
        pb_project = session.query(m.Project).filter(m.Project.key == "PB").one()

    create_response = client.post(
        "/assignments",
        headers=po_headers,
        json={
            "developer_id": developer.id,
            "project_id": pb_project.id,
            "role": "Engineer",
        },
    )
    assert create_response.status_code == 200, create_response.text
    payload = create_response.json()
    assert payload["project_id"] == pb_project.id
    assert payload["developer_id"] == developer.id

    list_response = client.get(f"/projects/{pb_project.id}/assignments", headers=po_headers)
    assert list_response.status_code == 200
    assignments = list_response.json()["assignments"]
    assert any(item["project_id"] == pb_project.id for item in assignments)

    dev_token = _get_token(client, "dev_alex")
    dev_claims = _decode_claims(dev_token)
    assert {"PX", "PB"}.issubset(set(dev_claims["accessible_projects"]))

    ba_token = _get_token(client, "ba_anita")
    ba_headers = {"Authorization": f"Bearer {ba_token}"}

    forbidden = client.post(
        "/assignments",
        headers=ba_headers,
        json={
            "developer_id": developer.id,
            "project_id": px_project.id,
            "role": "Engineer",
        },
    )
    assert forbidden.status_code == 403

    ba_list = client.get(f"/projects/{pb_project.id}/assignments", headers=ba_headers)
    assert ba_list.status_code == 200
    assert ba_list.json()["assignments"], "BA should be able to read assignments"
