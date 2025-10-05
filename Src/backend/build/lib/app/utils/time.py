# FILE: northstar/backend/app/time.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_utc() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Return the current UTC time formatted as ISO-8601."""

    return now_utc().strftime(ISO_FMT)


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware datetime."""

    if value.endswith("Z"):
        try:
            return datetime.strptime(value, ISO_FMT).replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_FACTORS = {"s":1, "m":60, "h":3600, "d":86400, "w":604800}

def parse_duration(value: str) -> int:
    """Parse strings like ``30s`` or ``2h`` into seconds."""

    match = _DURATION_RE.match(value or "")
    if not match:
        raise ValueError(f"Invalid duration: {value}")
    amount, unit = int(match.group(1)), match.group(2).lower()
    return amount * _FACTORS[unit]


def add_seconds(dt: datetime, secs: int) -> datetime:
    """Return ``dt`` shifted by ``secs`` seconds."""

    return dt + timedelta(seconds=secs)
