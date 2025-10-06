#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/North-Star/Src/backend"
PYTHON_EXE="$REPO_ROOT/venv/Scripts/python.exe"
if [[ ! -x "$PYTHON_EXE" ]]; then
  PYTHON_EXE="python"
fi

ARGS=("-m" "app.scripts.isolation_proof")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tests)
      ARGS+=("--skip-tests")
      shift
      ;;
    --output-dir)
      ARGS+=("--output-dir" "$2")
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

pushd "$BACKEND_DIR" >/dev/null
trap 'popd >/dev/null' EXIT

"$PYTHON_EXE" "${ARGS[@]}"
