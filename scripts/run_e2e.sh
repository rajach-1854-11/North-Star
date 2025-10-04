#!/usr/bin/env bash
set -euo pipefail
TS=$(date +"%Y%m%d-%H%M%S")
ARTIFACT_DIR="artifacts/e2e/${TS}"
mkdir -p "${ARTIFACT_DIR}"
python -m app.scripts.run_e2e --artifacts "${ARTIFACT_DIR}"
