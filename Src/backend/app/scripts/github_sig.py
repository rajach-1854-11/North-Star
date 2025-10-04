"""Compute GitHub webhook signatures using the configured secret."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path

from app.config import settings


def compute_signature(raw_bytes: bytes, secret: str) -> str:
    """Return the ``X-Hub-Signature-256`` header for ``raw_bytes``."""

    if not secret:
        raise ValueError("GitHub webhook secret is empty")
    digest = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute GitHub webhook signatures")
    parser.add_argument("path", type=Path, nargs="?", help="Path to JSON payload (defaults to stdin)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON prior to signing")
    args = parser.parse_args(argv)

    if args.path is None:
        data = sys.stdin.buffer.read()
    else:
        data = args.path.read_bytes()

    if args.pretty:
        try:
            parsed = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            raise SystemExit("Payload is not valid JSON; cannot pretty-print") from None
        data = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("utf-8")

    secret = settings.github_webhook_secret or ""
    try:
        signature = compute_signature(data, secret)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(signature)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
