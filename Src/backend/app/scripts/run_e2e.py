"""Deterministic end-to-end harness for the North Star platform."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import httpx
import jwt
import xml.etree.ElementTree as ET

try:  # Redis is optional when queue_mode != "redis"
    import redis  # type: ignore
except Exception:  # pragma: no cover - only hit if redis package missing
    redis = None

from sqlalchemy import text
from sqlalchemy.engine import Engine, URL, create_engine

from app.config import settings
from app.scripts.github_sig import compute_signature
from worker.handlers.evidence_builder import to_confluence_html

BASE_URL_DEFAULT = "http://127.0.0.1:9000"
UVICORN_PORT = 9000
READINESS_TIMEOUT = 60.0
READINESS_INTERVAL = 0.5
REQUEST_TIMEOUT = 20.0
MAX_ATTEMPTS = 5
BACKOFF_BASE = 0.5
BACKOFF_MAX = 6.0
BACKOFF_JITTER = 0.25
WEBHOOK_LOG_TIMEOUT = 20.0
LOG_POLL_INTERVAL = 0.5
SUMMARY_FILENAME = "summary.md"
PERF_JSON = "perf.json"
PERF_MD = "perf.md"
LATEST_ZIP_NAME = "latest.zip"
E2E_STATUS_FILENAME = "E2E_STATUS.txt"
PYTEST_STDOUT = "pytest.out.txt"
COVERAGE_XML = "coverage.xml"
JUNIT_XML = "junit.xml"

RESPONSE_FILES = {
    "openapi": "01_openapi.json",
    "auth_po": "02_auth_po.json",
    "auth_ba": "03_auth_ba.json",
    "auth_dev": "04_auth_dev.json",
    "project": "05_project_create.json",
    "upload": "06_upload_px.json",
    "retrieve_ba": "07_retrieve_ba.json",
    "retrieve_dev": "08_retrieve_dev.json",
    "agent_po": "09_agent_publish_po.json",
    "agent_dev": "10_agent_publish_dev.json",
    "github": "11_github_webhook.json",
}

API_USERS = {
    "po": {"username": "po_admin", "password": "x"},
    "ba": {"username": "ba_nancy", "password": "x"},
    "dev": {"username": "dev_alex", "password": "x"},
}

SAMPLE_PROJECT = {
    "key": "PX",
    "name": "Realtime Pricing",
    "description": "Streaming price calc and auth alignment",
}

GITHUB_EVENT_NAME = "push"
GITHUB_SAMPLE_PATH = Path("samples/github_push.json")
UPLOAD_SAMPLE_PATH = Path("samples/PX.md")
TRIAGE_DIRNAME = "triage"


def _percentile(sorted_samples: Sequence[float], q: float) -> float:
    if not sorted_samples:
        return math.nan
    if len(sorted_samples) == 1:
        return float(sorted_samples[0])
    idx = (len(sorted_samples) - 1) * q
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return float(sorted_samples[int(idx)])
    lower_value = sorted_samples[lower]
    upper_value = sorted_samples[upper]
    return float(lower_value + (upper_value - lower_value) * (idx - lower))


class StepFailure(RuntimeError):
    """Raised when a deterministic step in the harness fails."""


class ReadinessTimeout(StepFailure):
    """Raised when API readiness probing times out."""


@dataclass(slots=True)
class StepStatus:
    ok: bool = False
    detail: str = ""
    code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_path: Path
    stream_thread: threading.Thread


class Redactor:
    """Utility for masking secrets before persisting artifacts."""

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
        def _mask_uri(match: re.Match[str]) -> str:
            scheme = match.group("scheme")
            mask_scheme = scheme
            if scheme.lower() == "redis":
                mask_scheme = "rediss"
            return f"{mask_scheme}://***@"

        scrubbed = self._URI_CREDENTIAL_PATTERN.sub(_mask_uri, scrubbed)
        return scrubbed

    def redact_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: self.redact_json(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self.redact_json(item) for item in data]
        if isinstance(data, str):
            return self.redact_text(data)
        return data


def sanitize_url_for_snapshot(url: str, *, host_only: bool = False) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    if host_only:
        return f"{hostname}{port}".strip()
    scheme = parsed.scheme or "http"
    return f"{scheme}://{hostname}{port}".strip()


def build_env_fingerprint() -> list[str]:
    """Return a deterministic list of hashed environment variable names."""

    hashes = [hashlib.sha256(name.encode("utf-8")).hexdigest() for name in sorted(os.environ)]
    return sorted(hashes)


class E2EHarness:
    """Non-negotiable orchestration for the North Star acceptance flow."""

    def __init__(self, artifact_dir: Path, base_url: str, port: int) -> None:
        self.repo_root = Path(__file__).resolve().parents[5]
        self.backend_root = self.repo_root / "North-Star" / "Src" / "backend"
        self.artifact_dir = artifact_dir
        self.base_url = base_url.rstrip("/")
        self.port = port
        self.run_id = artifact_dir.name

        self.meta_dir = artifact_dir / "meta"
        self.logs_dir = artifact_dir / "logs"
        self.responses_dir = artifact_dir / "responses"
        self.proof_dir = artifact_dir / "proof"
        self.reports_dir = artifact_dir / "reports"
        self.bundle_dir = artifact_dir / "bundle"
        self.triage_dir = artifact_dir / TRIAGE_DIRNAME

        self.redactor = Redactor()
        self._register_initial_tokens()

        self.status: dict[str, Any] = {
            "preflight": StepStatus(),
            "openapi": StepStatus(),
            "auth": {role: StepStatus() for role in API_USERS},
            "project": StepStatus(),
            "upload": StepStatus(),
            "retrieve_ba": StepStatus(),
            "retrieve_dev": StepStatus(),
            "agent_po": StepStatus(),
            "agent_dev": StepStatus(),
            "github": StepStatus(),
            "isolation": StepStatus(),
            "pytest": StepStatus(),
        }

        self.tokens: dict[str, str] = {}
        self.notes: list[str] = []
        self.perf_samples: dict[str, list[float]] = defaultdict(list)
        self.perf_snapshot: dict[str, dict[str, Any]] = {}
        self.worker_handled_webhook = False
        self.worker_webhook_latency_ms: float | None = None
        self.pytest_totals: dict[str, int] = {}

        self._processes: list[ManagedProcess] = []

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------
    def run(self) -> int:
        started = time.monotonic()
        try:
            self._prepare_artifact_tree()
            preflight = self._run_preflight()
            self._write_preflight(preflight)
            self.status["preflight"].ok = preflight.get("ok", False)
            if not self.status["preflight"].ok:
                self.notes.append("Preflight checks reported issues; continuing.")

            with self._launch_services():
                self._wait_for_readiness()
                self._exercise_flow()
        except ReadinessTimeout as exc:
            self.status["openapi"].detail = str(exc)
            self.notes.append(f"API readiness timeout: {exc}")
            return self._finalise(started, success=False, exit_code=2)
        except StepFailure as exc:
            self.notes.append(str(exc))
            return self._finalise(started, success=False, exit_code=1)
        except Exception as exc:  # pragma: no cover - last resort logging
            self.notes.append(f"Unhandled error: {exc}")
            return self._finalise(started, success=False, exit_code=3)

        success = all(
            status.ok if isinstance(status, StepStatus) else all(role.ok for role in status.values())
            for status in self.status.values()
        )
        return self._finalise(started, success=success, exit_code=0 if success else 1)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _register_initial_tokens(self) -> None:
        candidates = [
            settings.jwt_secret,
            settings.jwt_aud or "",
            settings.postgres_password,
            settings.qdrant_api_key or "",
            settings.redis_url or "",
            settings.github_webhook_secret or "",
            settings.github_app_token or "",
            settings.atlassian_api_token or "",
            settings.atlassian_email or "",
        ]
        for value in candidates:
            self.redactor.register(value)

    def _prepare_artifact_tree(self) -> None:
        for directory in (
            self.artifact_dir,
            self.meta_dir,
            self.logs_dir,
            self.responses_dir,
            self.proof_dir,
            self.reports_dir,
            self.bundle_dir,
            self.triage_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        settings_snapshot = settings.model_dump(mode="json")
        sanitised = self.redactor.redact_json(settings_snapshot)
        (self.meta_dir / "settings_snapshot.json").write_text(
            json.dumps(sanitised, indent=2, sort_keys=True), encoding="utf-8"
        )

        fingerprint = "\n".join(build_env_fingerprint())
        (self.meta_dir / "env_fingerprint.txt").write_text(fingerprint, encoding="utf-8")

    def _build_postgres_engine(self) -> Engine:
        if settings.database_url:
            url = URL.create(settings.database_url)
        else:
            url = URL.create(
                "postgresql+psycopg",
                username=settings.postgres_user,
                password=settings.postgres_password,
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
            )
        return create_engine(url, connect_args={"connect_timeout": settings.postgres_connect_timeout or 30})

    def _run_preflight(self) -> dict[str, Any]:
        report: dict[str, Any] = {"ok": True, "postgres": {}, "qdrant": {}, "redis": {}}

        # PostgreSQL
        try:
            engine = self._build_postgres_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            report["postgres"] = {"ok": True, "dsn": sanitize_url_for_snapshot(str(engine.url))}
        except Exception as exc:  # pragma: no cover - depends on env
            report["postgres"] = {"ok": False, "detail": str(exc)}
            report["ok"] = False
            self.notes.append(f"Postgres preflight failed: {exc}")

        # Qdrant
        qdrant_url = settings.qdrant_url.rstrip("/")
        qdrant_headers = {}
        if settings.qdrant_api_key:
            qdrant_headers["api-key"] = settings.qdrant_api_key
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.get(f"{qdrant_url}/collections", headers=qdrant_headers)
                report["qdrant"] = {"ok": resp.is_success, "status": resp.status_code}
                if not resp.is_success:
                    report["ok"] = False
                    report["qdrant"]["detail"] = resp.text[:256]
        except Exception as exc:  # pragma: no cover - depends on env
            report["qdrant"] = {"ok": False, "detail": str(exc)}
            report["ok"] = False
            self.notes.append(f"Qdrant preflight failed: {exc}")

        # Redis (if applicable)
        if settings.queue_mode == "redis" and settings.redis_url and redis is not None:
            try:
                client = redis.from_url(settings.redis_url)
                client.ping()
                report["redis"] = {"ok": True, "url": sanitize_url_for_snapshot(settings.redis_url)}
            except Exception as exc:  # pragma: no cover - depends on env
                report["redis"] = {"ok": False, "detail": str(exc)}
                report["ok"] = False
                self.notes.append(f"Redis preflight failed: {exc}")
        elif settings.queue_mode == "redis":
            report["redis"] = {"ok": False, "detail": "redis package not installed"}
            report["ok"] = False
        else:
            report["redis"] = {"ok": True, "detail": "queue_mode=direct"}

        return report

    def _write_preflight(self, payload: Mapping[str, Any]) -> None:
        doc = self.redactor.redact_json(payload)
        (self.meta_dir / "preflight.json").write_text(
            json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
        )

    @contextlib.contextmanager
    def _launch_services(self) -> Iterable[None]:
        api_process = self._start_process(
            name="api",
            cmd=[
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(self.port),
            ],
            log_path=self.logs_dir / "api.log",
        )
        _ = api_process
        if settings.queue_mode == "redis" and settings.redis_url:
            self._start_process(
                name="worker",
                cmd=[sys.executable, "-m", "worker.main"],
                log_path=self.logs_dir / "worker.log",
            )
        try:
            yield
        finally:
            for managed in reversed(self._processes):
                proc = managed.process
                if proc.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        proc.send_signal(signal.SIGINT)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                managed.stream_thread.join(timeout=5)

    def _start_process(self, name: str, cmd: list[str], log_path: Path) -> ManagedProcess:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            cmd,
            cwd=self.backend_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        thread = threading.Thread(
            target=self._stream_process_output,
            args=(name, process, log_path),
            daemon=True,
        )
        thread.start()
        managed = ManagedProcess(name=name, process=process, log_path=log_path, stream_thread=thread)
        self._processes.append(managed)
        return managed

    def _stream_process_output(self, name: str, proc: subprocess.Popen[str], log_path: Path) -> None:
        del name
        with log_path.open("w", encoding="utf-8", buffering=1) as handle:
            if not proc.stdout:
                return
            for line in proc.stdout:
                handle.write(self.redactor.redact_text(line))

    def _wait_for_readiness(self) -> None:
        deadline = time.monotonic() + READINESS_TIMEOUT
        url = f"{self.base_url}/openapi.json"
        last_error: str | None = None
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            while time.monotonic() < deadline:
                try:
                    resp = client.get(url)
                    if resp.is_success:
                        self.status["openapi"].ok = True
                        self._record_response("openapi", resp)
                        return
                    last_error = f"HTTP {resp.status_code}"
                except Exception as exc:
                    last_error = str(exc)
                time.sleep(READINESS_INTERVAL)
        raise ReadinessTimeout(last_error or "timed out waiting for /openapi.json")

    # ------------------------------------------------------------------
    # Flow orchestration
    # ------------------------------------------------------------------
    def _exercise_flow(self) -> None:
        with httpx.Client(base_url=self.base_url, timeout=REQUEST_TIMEOUT) as client:
            self._authenticate(client)
            self._ensure_project(client)
            self._upload_sample(client)
            self._retrieve_checks(client)
            self._agent_publish(client)
            self._trigger_webhook(client)
        self._run_isolation_proof()
        self._run_pytest()

    def _request_with_retry(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        label: str,
        token: str | None = None,
        expected: Sequence[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        if token:
            headers = {"Authorization": f"Bearer {token}", **headers}
        attempt = 0
        expected_codes = set(expected or {200})
        while attempt < MAX_ATTEMPTS:
            attempt += 1
            started = time.perf_counter()
            try:
                resp = client.request(method, url, headers=headers, **kwargs)
                duration_ms = (time.perf_counter() - started) * 1000
                self.perf_samples[label].append(duration_ms)
                if resp.status_code in expected_codes:
                    return resp
                detail = resp.text[:512]
                if attempt >= MAX_ATTEMPTS:
                    raise StepFailure(f"{label} failed with HTTP {resp.status_code}: {detail}")
            except httpx.RequestError as exc:
                if attempt >= MAX_ATTEMPTS:
                    raise StepFailure(f"{label} request error: {exc}")
                detail = str(exc)
            sleep_for = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (attempt - 1)))
            sleep_for += random.uniform(0, BACKOFF_JITTER)
            time.sleep(sleep_for)
        raise StepFailure(f"{label} exhausted retries")

    def _record_response(self, key: str, response: httpx.Response) -> None:
        filename = RESPONSE_FILES.get(key)
        if not filename:
            return
        path = self.responses_dir / filename
        try:
            data = response.json()
            content = json.dumps(self.redactor.redact_json(data), indent=2, sort_keys=True)
        except ValueError:
            content = self.redactor.redact_text(response.text)
        path.write_text(content, encoding="utf-8")

    def _authenticate(self, client: httpx.Client) -> None:
        for role, creds in API_USERS.items():
            resp = self._request_with_retry(
                client,
                "post",
                "/auth/token",
                label=f"auth_{role}",
                params={"username": creds["username"], "password": creds["password"]},
            )
            self._record_response(f"auth_{role}", resp)
            payload = resp.json()
            token = payload.get("access_token")
            if not token:
                raise StepFailure(f"auth_{role} did not return a token")
            self.tokens[role] = token
            self.redactor.register(token)
            self.status["auth"][role].ok = True
            claims = jwt.decode(token, options={"verify_signature": False})
            (self.meta_dir / f"claims_{role}.json").write_text(
                json.dumps(claims, indent=2, sort_keys=True), encoding="utf-8"
            )

    def _ensure_project(self, client: httpx.Client) -> None:
        token = self.tokens.get("po")
        if not token:
            raise StepFailure("PO token missing before project creation")
        resp = self._request_with_retry(
            client,
            "post",
            "/projects",
            label="project",
            token=token,
            params=SAMPLE_PROJECT,
            expected=(200, 409),
        )
        self._record_response("project", resp)
        self.status["project"].ok = resp.status_code in {200, 409}
        self.status["project"].code = resp.status_code
        if resp.status_code == 409:
            self.status["project"].detail = "already exists"

    def _upload_sample(self, client: httpx.Client) -> None:
        token = self.tokens.get("po")
        if not token:
            raise StepFailure("PO token missing before upload")
        sample_path = self.backend_root / UPLOAD_SAMPLE_PATH
        if not sample_path.exists():
            raise StepFailure(f"Sample file missing: {sample_path}")
        files = {"file": (sample_path.name, sample_path.read_bytes(), "text/markdown")}
        data = {"project_key": SAMPLE_PROJECT["key"]}
        resp = self._request_with_retry(
            client,
            "post",
            "/upload",
            label="upload",
            token=token,
            files=files,
            data=data,
        )
        self._record_response("upload", resp)
        payload = resp.json()
        self.status["upload"].ok = True
        self.status["upload"].metadata.update({"chunks": payload.get("chunks"), "count": payload.get("count")})

    def _retrieve_checks(self, client: httpx.Client) -> None:
        payload = {
            "query": "What is the PX project about?",
            "targets": [SAMPLE_PROJECT["key"]],
            "k": 6,
            "strategy": "qdrant",
        }
        for role in ("ba", "dev"):
            resp = self._request_with_retry(
                client,
                "post",
                "/retrieve",
                label=f"retrieve_{role}",
                token=self.tokens.get(role),
                json=payload,
            )
            self._record_response(f"retrieve_{role}", resp)
            data = resp.json()
            hits = len(data.get("results", []))
            key = f"retrieve_{role}"
            self.status[key].ok = resp.is_success and hits >= (1 if role == "ba" else 0)
            self.status[key].metadata["hits"] = hits

    def _agent_publish(self, client: httpx.Client) -> None:
        token_po = self.tokens.get("po")
        if not token_po:
            raise StepFailure("PO token missing before agent publish")
        space_key = settings.atlassian_space or "PXSPACE"
        evidence = "Harness automated PX summary"
        body_html = to_confluence_html(evidence)
        overrides = {
            "jira_epic": {
                "project_key": SAMPLE_PROJECT["key"],
                "summary": "PX automation readiness",
                "description": "Automated epic created by the harness.",
                "labels": ["automation", "px"],
            },
            "confluence_page": {
                "space_key": space_key,
                "title": f"PX Automation Report {datetime.now(timezone.utc):%Y-%m-%d}",
                "body_html": body_html,
            },
        }
        prompt = "Generate a PX program status update and publish artifacts."

        po_resp = self._request_with_retry(
            client,
            "post",
            "/agent/query",
            label="agent_po",
            token=token_po,
            json={
                "prompt": prompt,
                "targets": [SAMPLE_PROJECT["key"]],
                "tool_overrides": overrides,
            },
        )
        self._record_response("agent_po", po_resp)
        try:
            po_payload = po_resp.json()
        except ValueError:
            po_payload = {}
        fallback_message = (po_payload.get("message") or "").lower()
        self.status["agent_po"].ok = po_resp.is_success
        self.status["agent_po"].metadata["agent_retry"] = "fallback" in fallback_message
        if not po_resp.is_success:
            detail = po_payload.get("message") or po_resp.text[:256]
            self.status["agent_po"].detail = detail
            raise StepFailure(f"Agent publish (PO) failed: {detail}")

        dev_resp = self._request_with_retry(
            client,
            "post",
            "/agent/query",
            label="agent_dev",
            token=self.tokens.get("dev"),
            json={
                "prompt": prompt,
                "targets": [SAMPLE_PROJECT["key"]],
                "tool_overrides": overrides,
            },
            expected=(200, 403),
        )
        self._record_response("agent_dev", dev_resp)
        self.status["agent_dev"].code = dev_resp.status_code
        if dev_resp.status_code == 403:
            self.status["agent_dev"].ok = True
            self.status["agent_dev"].detail = "RBAC enforced"
        else:
            self.status["agent_dev"].ok = dev_resp.is_success
            if not dev_resp.is_success:
                raise StepFailure(f"Agent publish (Dev) unexpected failure: {dev_resp.text[:256]}")

    def _trigger_webhook(self, client: httpx.Client) -> None:
        sample_path = self.backend_root / GITHUB_SAMPLE_PATH
        if not sample_path.exists():
            raise StepFailure(f"GitHub sample payload missing: {sample_path}")
        body = sample_path.read_bytes()

        headers = {
            "X-GitHub-Event": GITHUB_EVENT_NAME,
            "Content-Type": "application/json",
        }
        if settings.github_webhook_secret:
            try:
                headers["X-Hub-Signature-256"] = compute_signature(body, settings.github_webhook_secret)
            except ValueError as exc:
                self._write_triage("triage_github.md", "GitHub webhook secret missing", str(exc))
                raise StepFailure("GitHub webhook secret missing or invalid") from exc
        else:
            self.notes.append("GitHub webhook secret not configured; request may fail.")

        started = time.perf_counter()
        resp = self._request_with_retry(
            client,
            "post",
            "/events/github",
            label="github",
            headers=headers,
            content=body,
            expected=(200, 202, 409),
        )
        self._record_response("github", resp)
        self.status["github"].code = resp.status_code
        if not resp.is_success:
            self.status["github"].detail = resp.text[:256]
            if resp.status_code in {401, 403}:
                self._write_triage(
                    "triage_github.md",
                    "GitHub webhook rejected",
                    "Verify GITHUB_WEBHOOK_SECRET and GitHub app configuration.",
                )
                raise StepFailure("GitHub webhook rejected due to authentication failure")
            raise StepFailure(f"GitHub webhook failed: HTTP {resp.status_code}")

        handled, latency_ms = self._await_worker_webhook(started)
        self.worker_handled_webhook = handled
        self.worker_webhook_latency_ms = latency_ms
        self.status["github"].metadata["worker_latency_ms"] = latency_ms
        self.status["github"].metadata["worker_confirmed"] = handled
        self.status["github"].ok = handled
        if not handled:
            raise StepFailure("Worker did not confirm GitHub webhook processing")

    def _await_worker_webhook(self, started: float) -> tuple[bool, float | None]:
        log_path = self.logs_dir / "worker.log"
        pattern = re.compile(r"github_handler processing webhook", re.IGNORECASE)
        deadline = time.monotonic() + WEBHOOK_LOG_TIMEOUT
        last_seen = ""
        while time.monotonic() < deadline:
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8", errors="ignore")
                if text != last_seen:
                    last_seen = text
                    if pattern.search(text):
                        latency = (time.perf_counter() - started) * 1000
                        return True, latency
            time.sleep(LOG_POLL_INTERVAL)
        return False, None

    def _run_isolation_proof(self) -> None:
        base_dir = Path(settings.isolation_report_dir).resolve()
        before = {p for p in base_dir.glob("*") if p.is_dir()} if base_dir.exists() else set()
        script_ps1 = self.repo_root / "run_isolation_proof.ps1"
        script_sh = self.repo_root / "run_isolation_proof.sh"
        if sys.platform.startswith("win") and script_ps1.exists():
            cmd = [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_ps1),
                "--OutputDir",
                str(base_dir),
            ]
        elif script_sh.exists():
            cmd = ["bash", str(script_sh), "--output-dir", str(base_dir)]
        else:
            self.notes.append("Isolation proof script missing; skipping run.")
            self.status["isolation"].detail = "script missing"
            return

        proc = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        invocation_log = "\n".join([
            "Command: " + " ".join(cmd),
            "Return code: " + str(proc.returncode),
            "--- stdout ---",
            self.redactor.redact_text(proc.stdout),
            "--- stderr ---",
            self.redactor.redact_text(proc.stderr),
        ])
        (self.proof_dir / "isolation_invocation.txt").write_text(invocation_log, encoding="utf-8")

        if proc.returncode != 0:
            self.status["isolation"].detail = "isolation proof script failed"
            raise StepFailure("Isolation proof execution failed")

        after = {p for p in base_dir.glob("*") if p.is_dir()}
        new_dirs = sorted(after - before, key=lambda p: p.stat().st_mtime)
        target_dir = new_dirs[-1] if new_dirs else None
        if target_dir:
            for item in target_dir.iterdir():
                dest = self.proof_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        self.status["isolation"].ok = True

    def _run_pytest(self) -> None:
        junit_path = self.reports_dir / JUNIT_XML
        coverage_path = self.reports_dir / COVERAGE_XML
        pytest_stdout = self.reports_dir / PYTEST_STDOUT

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={junit_path}",
            f"--cov=app",
            f"--cov=worker",
            f"--cov-report=xml:{coverage_path}",
            "--cov-report=term",
        ]
        env = os.environ.copy()
        proc = subprocess.run(cmd, cwd=self.backend_root, capture_output=True, text=True, env=env)

        stdout_text = self.redactor.redact_text(proc.stdout)
        stderr_text = self.redactor.redact_text(proc.stderr)
        pytest_stdout.write_text(stdout_text + "\n" + stderr_text, encoding="utf-8")

        self.status["pytest"].ok = proc.returncode == 0
        if proc.returncode != 0:
            self.status["pytest"].detail = "pytest reported failures"

        if junit_path.exists():
            self._collect_pytest_totals(junit_path)

    def _collect_pytest_totals(self, junit_path: Path) -> None:
        try:
            tree = ET.parse(junit_path)
            root = tree.getroot()
        except ET.ParseError:
            return
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0)) + int(root.attrib.get("errors", 0))
        self.pytest_totals = {"tests": tests, "failures": failures}

    def _snapshot_perf(self) -> None:
        snapshot: dict[str, dict[str, Any]] = {}
        all_samples: list[float] = []
        for label, samples in sorted(self.perf_samples.items()):
            if not samples:
                continue
            values = sorted(samples)
            all_samples.extend(values)
            snapshot[label] = {
                "count": len(values),
                "p50_ms": round(_percentile(values, 0.50), 2),
                "p95_ms": round(_percentile(values, 0.95), 2),
                "p99_ms": round(_percentile(values, 0.99), 2),
            }
        if all_samples:
            values = sorted(all_samples)
            snapshot["_aggregate"] = {
                "count": len(values),
                "p50_ms": round(_percentile(values, 0.50), 2),
                "p95_ms": round(_percentile(values, 0.95), 2),
                "p99_ms": round(_percentile(values, 0.99), 2),
            }
        if self.worker_webhook_latency_ms is not None:
            snapshot.setdefault("worker", {})["dequeue_latency_ms"] = round(self.worker_webhook_latency_ms, 2)
        self.perf_snapshot = snapshot

    def _write_perf_reports(self) -> None:
        if not self.perf_snapshot:
            return
        (self.reports_dir / PERF_JSON).write_text(
            json.dumps(self.perf_snapshot, indent=2, sort_keys=True), encoding="utf-8"
        )
        lines = ["| Step | Count | p50 (ms) | p95 (ms) | p99 (ms) |", "| ---- | -----: | -------: | -------: | -------: |"]
        for name, data in self.perf_snapshot.items():
            if name == "worker":
                continue
            lines.append(
                f"| {name} | {data.get('count', '-')} | {data.get('p50_ms', '-')} | {data.get('p95_ms', '-')} | {data.get('p99_ms', '-')} |"
            )
        if worker := self.perf_snapshot.get("worker"):
            lines.append("")
            lines.append(f"Worker dequeue latency: **{worker.get('dequeue_latency_ms', '-')} ms**")
        (self.reports_dir / PERF_MD).write_text("\\n".join(lines) + "\\n", encoding="utf-8")

    def _write_summary(self) -> None:
        lines: list[str] = []
        lines.append("# E2E Summary")
        lines.append("")
        lines.append(f"**Run ID:** {self.run_id}  ")
        lines.append(f"**Tenant:** {settings.tenant_id}  ")
        lines.append(f"**LLM Provider:** {settings.llm_provider}  ")
        lines.append(f"**Queue Mode:** {settings.queue_mode}  ")
        lines.append(f"**Draft Mode:** {str(bool(settings.confluence_draft_mode)).lower()}  ")
        lines.append("")
        lines.append("## Checklist")
        lines.append("")

        auth_ok = all(self.status["auth"][role].ok for role in ("po", "ba", "dev"))
        lines.append(f"Auth {self._icon(auth_ok)} (PO/BA/Dev tokens)")

        project_code = self.status["project"].code or 0
        if project_code == 200:
            project_status = "✅"
            project_detail = "created"
        elif project_code == 409:
            project_status = "⚠️"
            project_detail = "already exists"
        else:
            project_status = "❌"
            project_detail = f"code {project_code}"
        lines.append(f"Project create/idempotent {project_status} ({project_detail})")

        upload_status = self._icon(self.status["upload"].ok)
        lines.append(f"Upload {upload_status}")

        retrieve_hits = self.status["retrieve_ba"].metadata.get("hits", 0)
        retrieve_status = self._icon(self.status["retrieve_ba"].ok and retrieve_hits)
        lines.append(f"Retrieve (≥1 hit) {retrieve_status} (hits={retrieve_hits})")

        agent_po_ok = self.status["agent_po"].ok
        agent_po_icon = self._icon(agent_po_ok)
        if self.status["agent_po"].metadata.get("agent_retry"):
            agent_po_icon = "⚠️"
        agent_po_detail = self.status["agent_po"].detail or ""
        retry_note = " (retry applied)" if self.status["agent_po"].metadata.get("agent_retry") else ""
        detail_suffix = f" ({agent_po_detail})" if agent_po_detail else ""
        lines.append(f"Agent publish (PO) {agent_po_icon}{retry_note}{detail_suffix}")

        agent_dev_icon = self._icon(self.status["agent_dev"].ok)
        lines.append(f"Agent publish (Dev) {agent_dev_icon} (RBAC expected)")

        webhook_icon = self._icon(self.status["github"].ok and self.worker_handled_webhook)
        worker_latency = self.status["github"].metadata.get("worker_latency_ms")
        latency_note = f", worker latency {worker_latency:.2f} ms" if isinstance(worker_latency, (int, float)) else ""
        lines.append(f"Webhook end-to-end {webhook_icon}{latency_note}")

        lines.append(f"Isolation proof {self._icon(self.status['isolation'].ok)}")

        pytest_icon = self._icon(self.status["pytest"].ok)
        tests = self.pytest_totals.get("tests") or 0
        failures = self.pytest_totals.get("failures") or 0
        lines.append(f"Tests (pytest + coverage) {pytest_icon} (tests={tests}, failures={failures})")

        lines.append("")
        lines.append("## Performance (ms)")
        lines.append("")
        perf = self.perf_snapshot or {}
        if perf:
            lines.append("| Step | p50 | p95 | p99 |")
            lines.append("| ---- | --- | --- | --- |")
            for name, data in perf.items():
                if name in {"worker", "_aggregate"}:
                    continue
                lines.append(
                    f"| {name} | {data.get('p50_ms', '-')} | {data.get('p95_ms', '-')} | {data.get('p99_ms', '-')} |"
                )
            aggregate = perf.get("_aggregate")
            if aggregate:
                lines.append(
                    f"| aggregate | {aggregate.get('p50_ms', '-')} | {aggregate.get('p95_ms', '-')} | {aggregate.get('p99_ms', '-')} |"
                )
            worker_perf = perf.get("worker")
            if worker_perf:
                lines.append("")
                lines.append(
                    f"Worker dequeue latency: **{worker_perf.get('dequeue_latency_ms')} ms**"
                )
        else:
            lines.append("No HTTP calls recorded.")

        lines.append("")
        lines.append("## Notes")
        lines.append("")
        if self.notes:
            for note in self.notes:
                lines.append(f"- {note}")
        else:
            lines.append("- None")

        lines.append("")
        summary_path = self.reports_dir / SUMMARY_FILENAME
        summary_path.write_text("\n".join(lines), encoding="utf-8")

    def _icon(self, ok: bool) -> str:
        return "✅" if ok else "❌"

    def _write_status(self, success: bool) -> str:
        status_line = f"E2E_STATUS: {'PASS' if success else 'FAIL'}  ARTIFACT_DIR={self.artifact_dir}"
        status_path = self.artifact_dir / E2E_STATUS_FILENAME
        status_path.write_text(status_line + "\n", encoding="utf-8")

        latest_dir = self.artifact_dir.parent / "latest"
        if latest_dir.exists():
            if latest_dir.is_symlink() or latest_dir.is_file():
                latest_dir.unlink()
            else:
                shutil.rmtree(latest_dir)
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / E2E_STATUS_FILENAME).write_text(status_line + "\n", encoding="utf-8")
        (latest_dir / "ARTIFACT_POINTER.txt").write_text(str(self.artifact_dir), encoding="utf-8")
        return status_line

    def _write_bundle(self) -> None:
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            temp_path = Path(tmp.name)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in self.artifact_dir.iterdir():
                if path.name == "bundle":
                    continue
                self._add_to_zip(zf, path, self.artifact_dir.parent)
        bundle_path = self.bundle_dir / LATEST_ZIP_NAME
        if bundle_path.exists():
            bundle_path.unlink()
        shutil.move(str(temp_path), bundle_path)

    def _add_to_zip(self, zf: zipfile.ZipFile, path: Path, base: Path) -> None:
        if path.is_dir():
            for child in path.iterdir():
                self._add_to_zip(zf, child, base)
        else:
            arcname = path.relative_to(base)
            zf.write(path, arcname.as_posix())

    def _write_triage(self, filename: str, title: str, detail: str) -> None:
        self.triage_dir.mkdir(parents=True, exist_ok=True)
        path = self.triage_dir / filename
        lines = [f"# {title}", "", detail.strip(), ""]
        path.write_text("\n".join(lines), encoding="utf-8")

    def _finalise(self, started: float, *, success: bool, exit_code: int) -> int:
        self._snapshot_perf()
        self._write_perf_reports()
        self._write_summary()
        status_line = self._write_status(success)
        try:
            self._write_bundle()
        except Exception as exc:  # pragma: no cover - bundle best effort
            self.notes.append(f"Failed to create bundle: {exc}")
        duration = time.monotonic() - started
        print(f"{status_line}  DURATION={duration:.2f}s")
        return exit_code


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Non-Negotiable North Star E2E harness")
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="Path to the artifact directory (default: artifacts/e2e/<timestamp>)",
    )
    parser.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Base URL for the API")
    parser.add_argument("--port", type=int, default=UVICORN_PORT, help="Port to bind uvicorn")
    return parser.parse_args(list(argv) if argv is not None else None)


def resolve_artifact_dir(repo_root: Path, provided: Path | None) -> Path:
    if provided is not None:
        return provided.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return (repo_root / "artifacts" / "e2e" / timestamp).resolve()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[5]
    artifact_dir = resolve_artifact_dir(repo_root, args.artifacts)
    harness = E2EHarness(artifact_dir=artifact_dir, base_url=args.base_url, port=args.port)
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - filesystem specific
        print(f"Failed to prepare artifact directory: {exc}", file=sys.stderr)
        return 3
    return harness.run()


if __name__ == "__main__":
    raise SystemExit(main())

