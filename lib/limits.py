"""
Small brakes for the routes that fan out to other sites.

Only the einthusan routes do real work on this side: one scan reads a page per
language index, and einthusan answers a burst with thin pages that parse to
nothing. So one address gets a budget per minute, and only a few scans run at
once across the process — a visitor should never be able to turn the source
off for everybody else.
"""

import threading
import time

# Scans in flight at once. Enough for a few films at the same time, few enough
# that einthusan never sees a burst from this host.
SCAN_SLOTS = 4
SCAN_WAIT = 20

_buckets = {}
_guard = threading.Lock()
_slots = threading.BoundedSemaphore(SCAN_SLOTS)


def allow(key, limit, window):
    """(allowed, retry_after_seconds) for one address and one route."""
    now = time.time()
    with _guard:
        hits = _buckets.setdefault(key, [])
        hits[:] = [stamp for stamp in hits if now - stamp < window]
        if len(hits) >= limit:
            return False, max(1, int(window - (now - hits[0])) + 1)
        hits.append(now)
        if len(_buckets) > 4096:       # a bound on what a day of addresses costs
            for name in list(_buckets)[:1024]:
                _buckets.pop(name, None)
        return True, 0


class Busy(Exception):
    """Every scan slot stayed taken for longer than a request can wait."""


class scan_slot:
    """A place in the queue for one scan, and never forever."""

    def __enter__(self):
        if not _slots.acquire(timeout=SCAN_WAIT):
            raise Busy()
        return self

    def __exit__(self, *exc):
        _slots.release()
        return False
