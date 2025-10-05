"""Deterministic hashing utilities used across the application."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

try:
    import blake3

    _HAS_BLAKE3: Final[bool] = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    blake3 = None  # type: ignore[assignment]
    _HAS_BLAKE3 = False

Algo = Literal["blake3", "sha256"]

logger = logging.getLogger(__name__)


def _sort_key(value: Any) -> str:
    """Generate a JSON-based ordering key for arbitrary canonical values."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _stable_sequence(sequence: Iterable[Any], *, sort: bool = False) -> list[Any]:
    """Return a JSON-serialisable list with deterministic ordering."""

    items = [_canonicalise(item) for item in sequence]
    if sort:
        items = sorted(items, key=_sort_key)
    return items


def _canonicalise_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Create a mapping with deterministic keys and stable nested values."""

    return {key: _canonicalise(value) for key, value in sorted(mapping.items())}


def _canonicalise(value: Any) -> Any:
    """Convert arbitrary values into JSON-friendly deterministic forms."""

    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Mapping):
        return _canonicalise_mapping(value)
    if isinstance(value, set):
        return _stable_sequence(value, sort=True)
    if isinstance(value, (list, tuple)):
        return _stable_sequence(value)
    if is_dataclass(value):
        return _canonicalise_mapping(asdict(value))
    return value


def canonical_dumps(obj: Any) -> str:
    """Serialise *obj* to a deterministic JSON string."""

    return json.dumps(_canonicalise(obj), sort_keys=True, separators=(",", ":"))


def _normalise_key(key: bytes | str | None) -> bytes | None:
    """Normalise optional key inputs to raw bytes."""

    if key is None:
        return None
    if isinstance(key, bytes):
        return key
    return key.encode("utf-8")


def hash_bytes(data: bytes, *, algo: Algo = "blake3", key: bytes | str | None = None) -> str:
    """Hash raw bytes using the requested algorithm with optional keying."""

    key_bytes = _normalise_key(key)
    if algo == "blake3" and _HAS_BLAKE3:
        if key_bytes is not None:
            return blake3.blake3(key=key_bytes, data=data).hexdigest()
        return blake3.blake3(data).hexdigest()

    if algo == "blake3" and not _HAS_BLAKE3:
        logger.debug("blake3 unavailable; falling back to sha256 hashing")
        algo = "sha256"

    if key_bytes is not None:
        return hmac.new(key_bytes, data, digestmod=hashlib.sha256).hexdigest()
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def hash_text(
    text: str,
    *,
    encoding: str = "utf-8",
    algo: Algo = "blake3",
    key: bytes | str | None = None,
    namespace: str | None = None,
) -> str:
    """Hash textual input with stable encoding and optional namespace prefix."""

    payload = text.encode(encoding)
    if namespace:
        payload = f"{namespace}::".encode(encoding) + payload
    return hash_bytes(payload, algo=algo, key=key)


def hash_json(
    obj: Any,
    *,
    algo: Algo = "blake3",
    key: bytes | str | None = None,
    namespace: str | None = None,
) -> str:
    """Hash an arbitrary JSON-like structure deterministically."""

    serialised = canonical_dumps(obj).encode("utf-8")
    if namespace:
        serialised = f"{namespace}::".encode("utf-8") + serialised
    return hash_bytes(serialised, algo=algo, key=key)


def hash_args(
    obj: Any,
    *,
    algo: Algo = "blake3",
    key: bytes | str | None = None,
    namespace: str | None = None,
) -> str:
    """Backward compatible helper for hashing structured call arguments."""

    return hash_json(obj, algo=algo, key=key, namespace=namespace)


def hash_file(
    path: str | Path,
    *,
    algo: Algo = "blake3",
    key: bytes | str | None = None,
    chunk_size: int = 1 << 20,
) -> str:
    """Stream a file from disk and compute its digest."""

    file_path = Path(path)
    hasher = None
    key_bytes = _normalise_key(key)

    if algo == "blake3" and _HAS_BLAKE3:
        hasher = blake3.blake3(key=key_bytes) if key_bytes is not None else blake3.blake3()
    elif algo == "blake3" and not _HAS_BLAKE3:
        logger.debug("blake3 unavailable; falling back to sha256 hashing")
        algo = "sha256"

    if hasher is None:
        if key_bytes is not None:
            return _hash_file_hmac(file_path, key_bytes, chunk_size)
        hasher = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _hash_file_hmac(file_path: Path, key: bytes, chunk_size: int) -> str:
    """Compute an HMAC-SHA256 digest for a file stream."""

    mac = hmac.new(key, digestmod=hashlib.sha256)
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            mac.update(chunk)
    return mac.hexdigest()
