#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:9000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/North-Star/Src/backend"
SEED_DIR="$BACKEND_DIR/data/seed"
PX_DOC="$SCRIPT_DIR/PX.md"

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

export PX_DOC

pushd "$BACKEND_DIR" >/dev/null
"$PYTHON" -m app.scripts.data_seeder --dir "$SEED_DIR" --tenant tenant1 --dry-run --stats
"$PYTHON" -m app.scripts.data_seeder --dir "$SEED_DIR" --tenant tenant1
"$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 9000 &
UVICORN_PID=$!
trap 'kill $UVICORN_PID' EXIT
popd >/dev/null

sleep 8

"$PYTHON" <<'PY'
import json
import os
import sys
from pathlib import Path

import requests

BASE = "http://localhost:9000"
SESSION = requests.Session()
TIMEOUT = 15


def token(username: str) -> str:
    resp = SESSION.post(
        f"{BASE}/auth/token",
        params={"username": username, "password": "x"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def headers(user: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(user)}"}


def ensure_project(po_headers: dict[str, str]) -> None:
    resp = SESSION.post(
        f"{BASE}/projects",
        headers={**po_headers, "Content-Type": "application/json"},
        params={"key": "PX", "name": "Realtime Pricing", "description": "Pricing Platform"},
        timeout=TIMEOUT,
    )
    if resp.status_code not in (200, 409):
        raise RuntimeError(f"Project creation failed: {resp.status_code} {resp.text}")


def upload_document(po_headers: dict[str, str]) -> None:
    px_md = Path(os.environ.get("PX_DOC", "PX.md"))
    with px_md.open("rb") as fh:
        files = {
            "project_key": (None, "PX"),
            "file": (px_md.name, fh, "text/markdown"),
        }
        resp = SESSION.post(
            f"{BASE}/upload",
            headers={"Authorization": po_headers["Authorization"]},
            files=files,
            timeout=TIMEOUT,
        )
    resp.raise_for_status()


def retrieve(headers_: dict[str, str]) -> None:
    payload = {"query": "pricing", "targets": ["PX"], "k": 6}
    resp = SESSION.post(
        f"{BASE}/retrieve",
        headers={**headers_, "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


def publish_as_ba(ba_headers: dict[str, str]) -> None:
    payload = {
        "prompt": "Create onboarding epic",
        "allowed_tools": ["jira_epic", "confluence_page"],
        "targets": ["PX"],
    }
    resp = SESSION.post(
        f"{BASE}/agent/query",
        headers={**ba_headers, "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code == 502:
        print("BA publish returned 502 – verify Atlassian credentials.", file=sys.stderr)
        return
    resp.raise_for_status()


def ba_cannot_cross_tenant(ba_headers: dict[str, str]) -> None:
    payload = {"query": "status", "targets": ["NON_EXISTENT"], "k": 1}
    resp = SESSION.post(
        f"{BASE}/retrieve",
        headers={**ba_headers, "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code != 403:
        raise RuntimeError(f"Expected 403 for cross-tenant retrieve, got {resp.status_code}")


admin_headers = headers("admin_root")
ba_headers = headers("ba_nancy")
po_headers = headers("po_admin")

audit = SESSION.get(f"{BASE}/admin/users", headers=admin_headers, timeout=TIMEOUT)
audit.raise_for_status()
ensure_project(po_headers)
upload_document(po_headers)
retrieve(po_headers)
retrieve(ba_headers)
publish_as_ba(ba_headers)
ba_cannot_cross_tenant(ba_headers)

print("Smoke test completed.")
PY
