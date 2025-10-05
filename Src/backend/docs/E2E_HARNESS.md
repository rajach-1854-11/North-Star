# Non-Negotiable E2E Harness

This document explains how to run the deterministic end-to-end harness and what
artifacts to expect when it completes.

## Prerequisites

- Python 3.12 with all backend dependencies installed (`pip install -e .[dev]`).
- Required environment variables populated (copy `.env.example` → `.env`).
- PostgreSQL, Qdrant, and Redis endpoints reachable with the credentials stored
  in your environment.

Run the harness from the backend project root:

```
North-Star/Src/backend
```

## Quick start

### Linux or macOS

```bash
./../../../scripts/run_e2e.sh
```

### Windows (PowerShell)

```powershell
../../..\scripts\run_e2e.ps1
```

Each wrapper script stamps a new artifact directory under
`artifacts/e2e/<YYYYmmdd-HHMMSS>` and invokes `python -m app.scripts.run_e2e`
with that path.

To run the module directly:

```bash
python -m app.scripts.run_e2e --artifacts artifacts/e2e/$(date +%Y%m%d-%H%M%S)
```

## What the harness does

1. Creates the full artifact layout (meta, logs, responses, proof, reports,
   bundle) and snapshots non-secret configuration + environment fingerprints.
2. Executes preflight checks for PostgreSQL, Qdrant, Redis (if configured), and
   records an informational report.
3. Launches `uvicorn app.main:app` on port 9000 and `python -m worker.main`,
   streaming redacted logs to `logs/api.log` and `logs/worker.log`.
4. Polls `GET /openapi.json` until readiness succeeds (timeout 60 seconds).
5. Exercises the full API workflow in order:
   - Auth tokens for `po_admin`, `ba_nancy`, `dev_alex`
   - Project PX creation / ensure
   - Uploads `samples/PX.md`
   - Uses BA and Dev tokens to query `/retrieve`
   - Agent publish with PO (expects Jira + Confluence artifacts when draft mode
     credentials exist) and Dev (expects RBAC denial)
   - Posts the signed GitHub webhook payload (`samples/github_push.json`) and
     confirms worker handling in the logs
6. Runs the isolation proof helper (`run_isolation_proof.sh` / `.ps1`) and copies
   `isolation_report.json` + `isolation_report.md` into the artifact tree.
7. Executes `pytest -q --cov` with JUnit + coverage XML reports and captures the
   terminal output.
8. Redacts all secrets (environment values, Bearer tokens, API keys, signatures,
   DSN credentials) from logs, responses, and reports before saving them.
9. Writes `reports/summary.md` following the mandated format and prints the
   machine-readable line: `E2E_STATUS: PASS|FAIL  ARTIFACT_DIR=<path>`.
10. Packages the entire run into `bundle/latest.zip` while keeping the rest of
    the artifact tree intact.

## Artifact layout

```
artifacts/
  e2e/
    <timestamp>/
      meta/
        settings_snapshot.json
        env_fingerprint.txt
        preflight.json
        claims_po.json
        claims_ba.json
        claims_dev.json
      logs/
        api.log
        worker.log
        worker_github_excerpt.log
      responses/
        01_openapi.json … 11_github_webhook.json
      proof/
        isolation_report.json
        isolation_report.md
        isolation_invocation.txt
      reports/
        junit.xml
        coverage.xml
        pytest.out.txt
        summary.md
      bundle/
        latest.zip
```

## Exit codes

| Code | Meaning                                                     |
|------|-------------------------------------------------------------|
| 0    | All acceptance criteria satisfied (PASS)                    |
| 1    | Harness ran but one or more acceptance checks failed        |
| 2    | API readiness timeout (no successful `/openapi.json` probe) |
| 3    | Unexpected orchestration error (filesystem, subprocess, etc.) |

## Troubleshooting tips

- Review `logs/api.log` and `logs/worker.log` first; they already have secrets
  redacted. The `worker_github_excerpt.log` file highlights the webhook handling
  snippet.
- Check `meta/preflight.json` for connectivity diagnostics when external
  services are unavailable.
- If isolation proof fails, inspect `proof/isolation_invocation.txt` for the
  captured stdout/stderr of the helper script.
- When pytest fails, `reports/pytest.out.txt` mirrors the console output and the
  JUnit report pinpoints individual failing tests.
