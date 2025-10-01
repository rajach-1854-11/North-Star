# optional convenience export so `from worker import enqueue_github_event` works
from __future__ import annotations

from .queue import enqueue_github_event

__all__ = ["enqueue_github_event"]