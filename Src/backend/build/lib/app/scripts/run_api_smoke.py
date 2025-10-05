"""Live environment API smoke tester for North Star."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import stat
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import httpx
import psycopg2
import redis
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[5]
ENV_PATH = BACKEND_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=False)

from app.config import settings  # noqa: E402  # isort:skip
from app.scripts.github_sig import compute_signature  # noqa: E402  # isort:skip

SUMMARY_NAME = "smoke_summary.md"
REQUEST_TIMEOUT = 25.0
READINESS_TIMEOUT = 60.0
READINESS_INTERVAL = 1.0
WEBHOOK_WAIT_TIMEOUT = 25.0
WEBHOOK_POLL_INTERVAL = 0.5
API_HOST = "http://127.0.0.1:9000"
API_CMD = [
    sys.executable,
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "9000",
]
WORKER_CMD = [sys.executable, "-m", "worker.main"]
RESPONSE_FILES = OrderedDict(
    [
        ("token", "01_auth_token.json"),
        ("project", "02_project.json"),
        ("upload", "03_upload.json"),
        ("retrieve", "04_retrieve.json"),
        ("staff", "05_staff_recommend.json"),
        ("onboarding", "06_onboarding_generate.json"),
        ("agent", "07_agent_query.json"),
        ("skills", "08_skills_profile.json"),
        ("audit", "09_audit.json"),
        ("github", "10_github_event.json"),
    ]
)
STEP_LABELS = OrderedDict(
    [
        ("env", "Env guardrails"),
        ("postgres", "Postgres connectivity"),
        ("qdrant", "Qdrant connectivity"),
        ("redis", "Redis connectivity"),
        ("readiness", "API readiness"),
        ("token", "Auth token"),
        ("project", "Project upsert"),
        ("upload", "Upload"),
        ("retrieve", "Retrieve"),
        ("staff", "Staff recommend"),
        ("onboarding", "Onboarding generate"),
        ("agent", "Agent query"),
        ("skills", "Skills profile"),
        ("audit", "Audit"),
        ("github", "GitHub webhook"),
    ]
)
WEBHOOK_PATTERN = re.compile(r"github_handler processing webhook", re.IGNORECASE)


def _remove_readonly(func: Any, path: str, exc: tuple[type[BaseException], BaseException, Any]) -> None:
    """Best-effort helper to clear read-only attributes then retry removal."""

    err = exc[1]
    if isinstance(err, PermissionError):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
            return
        except Exception:
            pass
    raise err


def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, onerror=_remove_readonly)


class StepFailure(RuntimeError):
    """Raised when a smoke step fails deterministically."""

    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step
        self.detail = message


class CredentialsBlocker(StepFailure):
    """Raised when a failure is due to missing or invalid credentials."""

    def __init__(self, step: str, env_vars: Sequence[str], message: str) -> None:
        super().__init__(step, message)
        self.env_vars = tuple(env_vars)


@dataclass(slots=True)
class StepStatus:
    ok: bool = False
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_path: Path
    stream_thread: threading.Thread


class Redactor:
    """Utility for masking secrets before writing logs or artifacts."""

    _HEADER_PATTERN = re.compile(
        r"(?im)^(?P<name>[\w-]*?(?:authorization|api[-_]key|token|secret)[\w-]*)\s*:\s*.*$"
    )
    _URI_CREDENTIAL_PATTERN = re.compile(
        r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://(?P<creds>[^@\s]+)@"
    )

    def __init__(self, seeds: Iterable[str] | None = None) -> None:
        self._tokens: set[str] = set()
        if seeds:
            for value in seeds:
                self.register(value)

    def register(self, value: str | None) -> None:
        if not value:
            return
        cleaned = value.strip()
        if cleaned:
            self._tokens.add(cleaned)

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        scrubbed = text
        for token in sorted(self._tokens, key=len, reverse=True):
            scrubbed = scrubbed.replace(token, "***")
        scrubbed = self._HEADER_PATTERN.sub(
            lambda match: f"{match.group('name')}: ***", scrubbed
        )
        scrubbed = self._URI_CREDENTIAL_PATTERN.sub(
            lambda match: f"{match.group('scheme')}://***@", scrubbed
        )
        return scrubbed

    def redact_json(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            return {key: self.redact_json(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self.redact_json(item) for item in payload]
        if isinstance(payload, str):
            return self.redact_text(payload)
        return payload


class APISmokeHarness:
    """Smoke orchestrator covering live-only endpoints."""

    def __init__(self, artifact_dir: Path, base_url: str = API_HOST) -> None:
        self.repo_root = REPO_ROOT
        self.backend_root = BACKEND_ROOT
        self.base_url = base_url.rstrip("/")
        self.artifact_dir = artifact_dir
        self.run_id = artifact_dir.name
        self.meta_dir = artifact_dir / "meta"
        self.logs_dir = artifact_dir / "logs"
        self.responses_dir = artifact_dir / "responses"
        self.reports_dir = artifact_dir / "reports"
        self.summary_path = self.reports_dir / SUMMARY_NAME

        seeds = [
            settings.jwt_secret,
            settings.qdrant_api_key or "",
            settings.redis_url or "",
            settings.github_webhook_secret or "",
            settings.cerebras_api_key or "",
            settings.atlassian_api_token or "",
        ]
        self.redactor = Redactor(seeds)

        self.statuses: OrderedDict[str, StepStatus] = OrderedDict(
            (key, StepStatus()) for key in STEP_LABELS
        )
        self._processes: list[ManagedProcess] = []
        self._blocker: CredentialsBlocker | None = None
        self._token: str | None = None
        self._project_id: int | None = None
        self._developer_id: int | None = None
        self._perf: dict[str, float] = {}
        self._notes: list[str] = []
        self._github_processed = False

    def run(self) -> int:
        started = time.monotonic()
        try:
            self._prepare_artifacts()
            self._ensure_remote_env()
            self._preflight_checks()
            with self._launch_processes():
                self._wait_for_readiness()
                self._exercise_flow()
        except CredentialsBlocker as blocker:
            self._blocker = blocker
            self._notes.append(blocker.detail)
        except StepFailure as failure:
            self._notes.append(failure.detail)
        except Exception as exc:  # pragma: no cover - unexpected failure surface
            self._notes.append(f"Unhandled error: {exc}")
        finally:
            success = all(status.ok for status in self.statuses.values())
            self._finalize(success, time.monotonic() - started)

        if self._blocker is not None:
            env_list = ", ".join(self._blocker.env_vars)
            print(f"CREDENTIALS BLOCKER: {env_list}", file=sys.stderr)
            print(self._blocker.detail, file=sys.stderr)
            return 2

        success = all(status.ok for status in self.statuses.values())
        return 0 if success else 1

    # ------------------------------------------------------------------
    # Setup & readiness
    # ------------------------------------------------------------------
    def _prepare_artifacts(self) -> None:
        for directory in (self.artifact_dir, self.logs_dir, self.responses_dir, self.reports_dir):
            directory.mkdir(parents=True, exist_ok=True)
        (self.meta_dir).mkdir(parents=True, exist_ok=True)
        (self.meta_dir / "settings_snapshot.json").write_text(
            json.dumps(self.redactor.redact_json(settings.model_dump(mode="json")), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (self.meta_dir / "run_id.txt").write_text(self.run_id, encoding="utf-8")

    def _ensure_remote_env(self) -> None:
        step = "env"
        status = self.statuses[step]
        messages: list[str] = []

        host = settings.postgres_host.lower()
        if host in {"localhost", "127.0.0.1", "postgres"}:
            status.detail = f"POSTGRES_HOST must be remote, found {settings.postgres_host}"
            raise StepFailure(step, status.detail)
        messages.append(f"Postgres host={settings.postgres_host}")

        if not re.match(r"https://.+\.cloud\.qdrant\.io/?", settings.qdrant_url):
            status.detail = f"QDRANT_URL must be a cloud endpoint, found {settings.qdrant_url}"
            raise StepFailure(step, status.detail)
        messages.append("Qdrant URL validated")

        if not settings.redis_url or not settings.redis_url.startswith("rediss://"):
            status.detail = "REDIS_URL must use rediss:// for Upstash TLS"
            raise StepFailure(step, status.detail)
        messages.append("Redis URL uses TLS")

        if settings.llm_provider != "cerebras" or not settings.cerebras_api_key:
            status.detail = "LLM provider must be cerebras with CEREBRAS_API_KEY set"
            raise StepFailure(step, status.detail)
        messages.append("Cerebras provider enforced")

        status.ok = True
        status.detail = "; ".join(messages)

    def _preflight_checks(self) -> None:
        self._check_postgres()
        self._check_qdrant()
        self._check_redis()

    def _check_postgres(self) -> None:
        step = "postgres"
        status = self.statuses[step]
        conn = None
        try:
            kwargs: dict[str, Any] = {
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "dbname": settings.postgres_db,
                "user": settings.postgres_user,
                "password": settings.postgres_password,
                "connect_timeout": settings.postgres_connect_timeout or 30,
            }
            if settings.postgres_sslmode:
                kwargs["sslmode"] = settings.postgres_sslmode
            if settings.postgres_sslrootcert:
                kwargs["sslrootcert"] = settings.postgres_sslrootcert
            conn = psycopg2.connect(**kwargs)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            status.ok = True
            status.detail = "SELECT 1 succeeded"
        except psycopg2.OperationalError as exc:
            message = str(exc)
            lowered = message.lower()
            if any(keyword in lowered for keyword in ("password", "authentication", "permission denied")):
                raise CredentialsBlocker(step, ["POSTGRES_PASSWORD"], f"Postgres auth failed: {message}")
            raise StepFailure(step, f"Postgres connectivity failed: {message}")
        except Exception as exc:  # pragma: no cover - defensive
            raise StepFailure(step, f"Postgres connectivity error: {exc}")
        finally:
            if conn is not None:
                conn.close()

    def _check_qdrant(self) -> None:
        step = "qdrant"
        status = self.statuses[step]
        headers = {}
        if settings.qdrant_api_key:
            headers["api-key"] = settings.qdrant_api_key
        url = settings.qdrant_url.rstrip("/") + "/"
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise StepFailure(step, f"Qdrant connectivity error: {exc}")
        if resp.status_code in {401, 403}:
            raise CredentialsBlocker(step, ["QDRANT_API_KEY"], f"Qdrant authentication failed: HTTP {resp.status_code}")
        if not resp.is_success:
            raise StepFailure(step, f"Qdrant health check failed: HTTP {resp.status_code}")
        status.ok = True
        status.detail = f"HTTP {resp.status_code}"

    def _check_redis(self) -> None:
        step = "redis"
        status = self.statuses[step]
        try:
            client = redis.from_url(settings.redis_url)  # type: ignore[arg-type]
            client.ping()
        except redis.AuthenticationError as exc:  # type: ignore[attr-defined]
            raise CredentialsBlocker(step, ["REDIS_URL"], f"Redis authentication failed: {exc}")
        except redis.ResponseError as exc:
            if "NOAUTH" in str(exc):
                raise CredentialsBlocker(step, ["REDIS_URL"], f"Redis authentication failed: {exc}")
            raise StepFailure(step, f"Redis response error: {exc}")
        except Exception as exc:
            raise StepFailure(step, f"Redis connectivity error: {exc}")
        status.ok = True
        status.detail = "PING succeeded"

    @contextlib.contextmanager
    def _launch_processes(self) -> Iterable[None]:
        self._processes.append(self._start_process("api", API_CMD, self.logs_dir / "api.log"))
        self._processes.append(self._start_process("worker", WORKER_CMD, self.logs_dir / "worker.log"))
        try:
            yield
        finally:
            for managed in reversed(self._processes):
                proc = managed.process
                if proc.poll() is None:
                    try:
                        if os.name == "nt":
                            proc.terminate()
                        else:
                            proc.send_signal(signal.SIGINT)
                        proc.wait(timeout=15)
                    except Exception:
                        proc.kill()
                managed.stream_thread.join(timeout=5)

    def _start_process(self, name: str, cmd: list[str], log_path: Path) -> ManagedProcess:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        process = subprocess.Popen(
            cmd,
            cwd=self.backend_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )
        thread = threading.Thread(
            target=self._stream_process_output,
            args=(process, log_path),
            name=f"{name}-log-writer",
            daemon=True,
        )
        thread.start()
        return ManagedProcess(name=name, process=process, log_path=log_path, stream_thread=thread)

    def _stream_process_output(self, proc: subprocess.Popen[str], log_path: Path) -> None:
        with log_path.open("w", encoding="utf-8", buffering=1) as handle:
            stdout = proc.stdout
            if stdout is None:
                return
            for line in stdout:
                handle.write(self.redactor.redact_text(line))

    def _wait_for_readiness(self) -> None:
        step = "readiness"
        status = self.statuses[step]
        url = f"{self.base_url}/openapi.json"
        deadline = time.monotonic() + READINESS_TIMEOUT
        last_error: str | None = None
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            while time.monotonic() < deadline:
                try:
                    resp = client.get(url)
                    if resp.is_success:
                        status.ok = True
                        status.detail = "openapi.json reachable"
                        return
                    last_error = f"HTTP {resp.status_code}"
                except Exception as exc:
                    last_error = str(exc)
                time.sleep(READINESS_INTERVAL)
        raise StepFailure(step, last_error or "timed out waiting for API readiness")

    # ------------------------------------------------------------------
    # Flow execution
    # ------------------------------------------------------------------
    def _exercise_flow(self) -> None:
        timeout = httpx.Timeout(REQUEST_TIMEOUT)
        with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
            self._token = self._obtain_token(client)
            project = self._ensure_project(client)
            self._project_id = project.get("id")
            self._upload_document(client)
            self._perform_retrieve(client)
            candidates = self._staff_recommend(client)
            if candidates:
                self._developer_id = candidates[0].get("developer_id")
            self._run_onboarding(client)
            self._agent_query(client)
            self._skills_profile(client)
            self._audit_logs(client)
            self._github_webhook(client)

    def _obtain_token(self, client: httpx.Client) -> str:
        step = "token"
        status = self.statuses[step]
        resp = client.post(
            "/auth/token",
            params={"username": "po_admin", "password": "x"},
        )
        self._write_response("token", resp)
        if resp.status_code == 401:
            raise CredentialsBlocker(step, ["JWT_SECRET"], "PO credentials rejected")
        if not resp.is_success:
            raise StepFailure(step, f"auth/token failed: HTTP {resp.status_code}")
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise StepFailure(step, "auth/token did not return access_token")
        self.redactor.register(token)
        status.ok = True
        status.detail = "Received bearer token"
        return token

    def _ensure_project(self, client: httpx.Client) -> dict[str, Any]:
        step = "project"
        status = self.statuses[step]
        params = {
            "key": "PX",
            "name": "Realtime Pricing",
            "description": "Smoke validation project",
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = client.post("/projects", params=params, headers=headers)
        self._write_response("project", resp)
        if resp.status_code not in {200, 409}:
            raise StepFailure(step, f"project create failed: HTTP {resp.status_code}")
        if resp.status_code == 409:
            # Fetch current project details for id reference
            detail = self._fetch_project(client, "PX", headers)
            status.ok = True
            status.detail = "Project exists"
            return detail
        payload = resp.json()
        status.ok = True
        status.detail = "Project created"
        return payload

    def _fetch_project(self, client: httpx.Client, key: str, headers: Mapping[str, str]) -> dict[str, Any]:
        resp = client.get(f"/projects/{key}", headers=headers)
        if not resp.is_success:
            raise StepFailure("project", f"Failed to fetch project {key}: HTTP {resp.status_code}")
        return resp.json()

    def _upload_document(self, client: httpx.Client) -> None:
        step = "upload"
        status = self.statuses[step]
        sample_path = self._ensure_sample_markdown()
        headers = {"Authorization": f"Bearer {self._token}"}
        files = {"file": (sample_path.name, sample_path.read_bytes(), "text/markdown")}
        data = {"project_key": "PX"}
        resp = client.post("/upload", headers=headers, files=files, data=data)
        self._write_response("upload", resp)
        if not resp.is_success:
            raise StepFailure(step, f"upload failed: HTTP {resp.status_code}")
        payload = resp.json()
        status.ok = True
        status.detail = f"Chunks={payload.get('chunks')}"

    def _perform_retrieve(self, client: httpx.Client) -> None:
        step = "retrieve"
        status = self.statuses[step]
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {
            "query": "compare PX vs PB auth and RBAC",
            "targets": ["PX", "PB"],
            "k": 6,
        }
        resp = client.post("/retrieve", headers=headers, json=payload)
        self._write_response("retrieve", resp)
        if not resp.is_success:
            raise StepFailure(step, f"retrieve failed: HTTP {resp.status_code}")
        results = resp.json().get("results", [])
        status.ok = True
        status.detail = f"Hits={len(results)}"

    def _staff_recommend(self, client: httpx.Client) -> list[dict[str, Any]]:
        step = "staff"
        status = self.statuses[step]
        if not self._project_id:
            raise StepFailure(step, "project id unavailable")
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {"project_id": self._project_id}
        resp = client.get("/staff/recommend", headers=headers, params=params)
        self._write_response("staff", resp)
        if not resp.is_success:
            raise StepFailure(step, f"staff recommend failed: HTTP {resp.status_code}")
        payload = resp.json()
        candidates = payload.get("candidates", [])
        status.ok = True
        status.detail = f"candidates={len(candidates)}"
        return candidates

    def _run_onboarding(self, client: httpx.Client) -> None:
        step = "onboarding"
        status = self.statuses[step]
        if not self._developer_id or not self._project_id:
            status.ok = True
            status.detail = "Skipped (no candidate)"
            return
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {
            "developer_id": self._developer_id,
            "project_id": self._project_id,
            "autonomy": "Ask",
        }
        resp = client.post("/onboarding/generate", headers=headers, json=payload)
        self._write_response("onboarding", resp)
        if not resp.is_success:
            raise StepFailure(step, f"onboarding failed: HTTP {resp.status_code}")
        status.ok = True
        status.detail = "Plan generated"

    def _agent_query(self, client: httpx.Client) -> None:
        step = "agent"
        status = self.statuses[step]
        headers = {"Authorization": f"Bearer {self._token}"}
        space_key = settings.atlassian_space or "PXSPACE"
        overrides = {
            "jira_epic": {
                "project_key": "PX",
                "summary": "PX smoke check",
                "description": "Automation smoke test",
            },
            "confluence_page": {
                "space_key": space_key,
                "title": f"PX Smoke Report {datetime.now(timezone.utc):%Y-%m-%d}",
                "body_html": "<p>Smoke validation draft.</p>",
                "draft_mode": True,
            },
        }
        payload = {
            "prompt": "Provide a PX status update and publish in draft mode.",
            "targets": ["PX"],
            "tool_overrides": overrides,
        }
        resp = client.post("/agent/query", headers=headers, json=payload)
        self._write_response("agent", resp)
        if resp.status_code in {401, 403, 502}:
            raise CredentialsBlocker(step, ["ATLASSIAN_API_TOKEN"], f"Agent query blocked: HTTP {resp.status_code}")
        if not resp.is_success:
            raise StepFailure(step, f"agent query failed: HTTP {resp.status_code}")
        data = resp.json()
        status.ok = True
        message = data.get("message") or "ok"
        status.detail = message[:120]

    def _skills_profile(self, client: httpx.Client) -> None:
        step = "skills"
        status = self.statuses[step]
        if not self._developer_id:
            status.ok = True
            status.detail = "Skipped (no candidate)"
            return
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {"developer_id": self._developer_id}
        resp = client.get("/skills/profile", headers=headers, params=params)
        self._write_response("skills", resp)
        if not resp.is_success:
            raise StepFailure(step, f"skills profile failed: HTTP {resp.status_code}")
        status.ok = True
        status.detail = "Profile fetched"

    def _audit_logs(self, client: httpx.Client) -> None:
        step = "audit"
        status = self.statuses[step]
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {"limit": 20}
        resp = client.get("/audit", headers=headers, params=params)
        self._write_response("audit", resp)
        if not resp.is_success:
            raise StepFailure(step, f"audit fetch failed: HTTP {resp.status_code}")
        status.ok = True
        status.detail = "Audit retrieved"

    def _github_webhook(self, client: httpx.Client) -> None:
        step = "github"
        status = self.statuses[step]
        sample_path = self.backend_root / "samples" / "github_push.json"
        if not sample_path.exists():
            raise StepFailure(step, f"Sample GitHub payload missing: {sample_path}")
        body = sample_path.read_bytes()
        headers = {
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": f"smoke-{uuid.uuid4()}",
        }
        if settings.github_webhook_secret:
            try:
                signature = compute_signature(body, settings.github_webhook_secret)
            except ValueError as exc:
                raise CredentialsBlocker(step, ["GITHUB_WEBHOOK_SECRET"], f"GitHub signature error: {exc}")
            headers["X-Hub-Signature-256"] = signature
        else:
            raise CredentialsBlocker(step, ["GITHUB_WEBHOOK_SECRET"], "GitHub webhook secret missing")

        resp = client.post("/events/github", headers=headers, content=body)
        self._write_response("github", resp)
        if resp.status_code in {401, 403}:
            raise CredentialsBlocker(step, ["GITHUB_WEBHOOK_SECRET"], f"GitHub webhook rejected: HTTP {resp.status_code}")
        if not resp.is_success:
            raise StepFailure(step, f"GitHub webhook failed: HTTP {resp.status_code}")

        self._github_processed = self._await_worker_confirmation()
        if not self._github_processed:
            raise StepFailure(step, "Worker did not log processing message")
        status.ok = True
        status.detail = "Worker processed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_sample_markdown(self) -> Path:
        sample_path = self.artifact_dir / "smoke_sample.md"
        if not sample_path.exists():
            sample_path.write_text("# PX Smoke Sample\n\nAutomated upload content.", encoding="utf-8")
        return sample_path

    def _write_response(self, key: str, response: httpx.Response) -> None:
        filename = RESPONSE_FILES.get(key)
        if not filename:
            return
        path = self.responses_dir / filename
        try:
            data = response.json()
            redacted = self.redactor.redact_json(data)
            content = json.dumps(redacted, indent=2, sort_keys=True)
        except ValueError:
            content = self.redactor.redact_text(response.text)
        path.write_text(content, encoding="utf-8")

    def _await_worker_confirmation(self) -> bool:
        log_path = self.logs_dir / "worker.log"
        deadline = time.monotonic() + WEBHOOK_WAIT_TIMEOUT
        last_len = 0
        while time.monotonic() < deadline:
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8", errors="ignore")
                if len(text) != last_len:
                    last_len = len(text)
                    if WEBHOOK_PATTERN.search(text):
                        return True
            time.sleep(WEBHOOK_POLL_INTERVAL)
        return False

    def _finalize(self, success: bool, duration: float) -> None:
        self._write_summary(success)
        self._write_latest()
        status_line = f"SMOKE_STATUS: {'PASS' if success else 'FAIL'}  RUN_ID={self.run_id}"
        print(f"{status_line}  DURATION={duration:.2f}s")

    def _write_summary(self, success: bool) -> None:
        lines: list[str] = []
        lines.append("# API Smoke Summary")
        lines.append("")
        lines.append(f"**Run ID:** {self.run_id}  ")
        lines.append(f"**Result:** {'PASS' if success else 'FAIL'}  ")
        lines.append(f"**Tenant:** {settings.tenant_id}  ")
        lines.append("")
        lines.append("## Checklist")
        lines.append("")
        for key, label in STEP_LABELS.items():
            status = self.statuses[key]
            icon = "✅" if status.ok else "❌"
            detail = status.detail or ""
            lines.append(f"- {label} {icon}: {detail}")
        lines.append("")
        lines.append("## Triage")
        lines.append("")
        failures = [
            (STEP_LABELS[key], status.detail)
            for key, status in self.statuses.items()
            if not status.ok
        ]
        if self._blocker is not None:
            env_list = ", ".join(self._blocker.env_vars)
            lines.append(f"- CREDENTIALS BLOCKER: {env_list} — {self._blocker.detail}")
        elif failures:
            for label, detail in failures:
                lines.append(f"- {label}: {detail or 'see logs'}")
        else:
            lines.append("- None")
        if self._notes:
            lines.append("")
            lines.append("## Notes")
            lines.append("")
            for note in self._notes:
                lines.append(f"- {self.redactor.redact_text(note)}")
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_latest(self) -> None:
        latest_dir = self.artifact_dir.parent / "latest"
        if latest_dir.exists():
            _safe_rmtree(latest_dir)
        shutil.copytree(self.artifact_dir, latest_dir)


def resolve_artifact_dir(provided: Path | None) -> Path:
    if provided is not None:
        return provided.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return (REPO_ROOT / "artifacts" / "smoke" / timestamp).resolve()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live API smoke test")
    parser.add_argument("--artifacts", type=Path, help="Optional artifact directory override")
    parser.add_argument(
        "--base-url",
        default=API_HOST,
        help="Base URL for the API (default http://127.0.0.1:9000)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifacts)
    harness = APISmokeHarness(artifact_dir=artifact_dir, base_url=args.base_url)
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - filesystem dependent
        print(f"Failed to prepare artifact directory: {exc}", file=sys.stderr)
        return 3
    return harness.run()


if __name__ == "__main__":
    raise SystemExit(main())
