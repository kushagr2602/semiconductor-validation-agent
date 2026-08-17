"""Spend guards for the public demo.

The deployed demo calls OpenAI with the owner's API key, so anything that can
reach the URL can spend real money. Two independent caps, both in-memory:

  per-IP    stops one visitor (or a crawler) looping the expensive endpoints
  global    stops the whole day's traffic exceeding a fixed budget

# ponytail: in-memory, so counters reset on restart and are per-process. That
# is correct for a single free-tier instance. Move to Redis only if the demo
# ever runs more than one worker.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

# Each guarded request makes 1-2 OpenAI calls, so these are call budgets, not
# request budgets -- keep them well under what you are willing to pay for.
PER_IP_LIMIT = int(os.getenv("DEMO_PER_IP_LIMIT", "10"))
PER_IP_WINDOW_S = int(os.getenv("DEMO_PER_IP_WINDOW_S", str(60 * 60)))  # 1 hour
GLOBAL_DAILY_LIMIT = int(os.getenv("DEMO_GLOBAL_DAILY_LIMIT", "200"))

_lock = threading.Lock()
_by_ip: dict[str, deque[float]] = defaultdict(deque)
_global: deque[float] = deque()


class RateLimited(Exception):
    """Raised when a caller is over budget. Carries a human-readable reason."""


def _prune(bucket: deque[float], window_s: float, now: float) -> None:
    while bucket and now - bucket[0] > window_s:
        bucket.popleft()


def check_and_consume(ip: str) -> None:
    """Record one billable request from `ip`, or raise RateLimited."""
    now = time.time()
    with _lock:
        _prune(_global, 24 * 60 * 60, now)
        if len(_global) >= GLOBAL_DAILY_LIMIT:
            raise RateLimited(
                "This demo has hit its daily budget. It resets within 24 hours -- "
                "run it locally with your own OpenAI key to keep exploring."
            )

        bucket = _by_ip[ip]
        _prune(bucket, PER_IP_WINDOW_S, now)
        if len(bucket) >= PER_IP_LIMIT:
            mins = max(1, int((PER_IP_WINDOW_S - (now - bucket[0])) / 60))
            raise RateLimited(
                f"You have used this demo's {PER_IP_LIMIT} requests per hour. "
                f"Try again in about {mins} minute(s)."
            )

        bucket.append(now)
        _global.append(now)


def usage() -> dict:
    """Current counters, surfaced in the UI so the limits are visible not surprising."""
    now = time.time()
    with _lock:
        _prune(_global, 24 * 60 * 60, now)
        return {
            "global_used": len(_global),
            "global_limit": GLOBAL_DAILY_LIMIT,
            "per_ip_limit": PER_IP_LIMIT,
            "per_ip_window_minutes": PER_IP_WINDOW_S // 60,
        }


def reset() -> None:
    """Test helper."""
    with _lock:
        _by_ip.clear()
        _global.clear()
