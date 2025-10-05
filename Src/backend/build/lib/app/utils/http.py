from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import httpx


@contextmanager
def sync_client(timeout: Optional[float] = 30) -> Iterator[httpx.Client]:
    """Yield a configured httpx.Client with reasonable defaults.

    This centralizes HTTP settings so adapters can share common behavior.
    """

    client = httpx.Client(timeout=timeout or 30)
    try:
        yield client
    finally:
        client.close()
