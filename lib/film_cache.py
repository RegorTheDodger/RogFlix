"""
What the fifth source already knows about a film.

Finding an Indian film on einthusan means reading one index page per language,
which costs seconds, and the answer does not change from one visitor to the
next. A Flask process on Vercel is thrown away between visitors, though, so the
answer is kept in the account database instead: for one IMDb id, the record
einthusan has in each language, the language the title matched best, and the
language the film was made in.

Two things follow from that. A cold instance no longer repeats a scan for a
film somebody already opened, and a scan for one film runs once even when
several people open it at the same moment.

None of it is required for playback: a database that is down or a row that
cannot be written only means the next visitor pays for the scan again.
"""

import json
import threading
import time

from . import db
from . import einthusan_source
from . import language
from . import limits

# einthusan adds and drops films, so an answer is reused for a few days rather
# than forever.
TTL = 3 * 24 * 3600
# Bumped when the shape of the answer changes, so a row written by an older
# version is scanned again instead of being served to everybody for a week.
CACHE_VERSION = 3
# How long a second visitor waits for a scan already in flight for this film.
MAX_WAIT = 20

_lock_guard = threading.Lock()
_locks = {}
# Title pages start their own scans, and a crawler reads a lot of title pages.
# Only a handful of those may be waiting at a time.
WARM_THREADS = 8
_warmers = [0]


class Busy(Exception):
    """The scan for this film is taking longer than a request can wait."""


def _lock(imdb):
    with _lock_guard:
        lock = _locks.get(imdb)
        if lock is None:
            lock = _locks[imdb] = threading.Lock()
            if len(_locks) > 4096:      # a bound on what a day of ids costs
                for key in list(_locks)[:1024]:
                    if key != imdb and not _locks[key].locked():
                        _locks.pop(key, None)
        return lock


def _row(imdb):
    try:
        rows = db.store().query(
            "SELECT at, data FROM iml_einthusan WHERE imdb = %s", (imdb,))
    except Exception:
        return None
    if not rows:
        return None
    at, raw = rows[0]
    try:
        fresh = time.time() - float(at or 0) <= TTL
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("matches") is None:
        return None
    try:
        current = int(data.get("v") or 0) >= CACHE_VERSION
    except (TypeError, ValueError):
        current = False
    return data if current else None


def _store(imdb, found, original):
    payload = {
        "v": CACHE_VERSION,
        "matches": found["by_lang"],
        "pick": found["pick"],
        "original": original,
    }
    try:
        db.store().run(
            "INSERT INTO iml_einthusan (imdb, at, data) VALUES (%s, %s, %s) "
            "ON CONFLICT (imdb) DO UPDATE SET at = EXCLUDED.at, "
            "data = EXCLUDED.data",
            (imdb, int(time.time()), json.dumps(payload)))
    except Exception:
        # a miss here costs the next visitor a scan, nothing more
        pass
    return payload


def peek(imdb):
    """What is already known, without doing any work over the network."""
    if not (imdb or "").strip():
        return None
    return _row(imdb)


def warm(imdb, name, year):
    """Everything einthusan has for this film, scanning only when needed."""
    cached = _row(imdb)
    if cached:
        return cached

    lock = _lock(imdb)
    if not lock.acquire(timeout=MAX_WAIT):
        raise Busy()
    try:
        cached = _row(imdb)            # somebody may have finished meanwhile
        if cached:
            return cached
        found = einthusan_source.find(name, year)
        if not found:
            return {"matches": {}, "pick": None, "original": ""}
        # A film einthusan carries several times is a different dub per index,
        # so the closest match is no sure guide to the original. Ask which
        # language it was made in, and if that index spells the title
        # differently, `find` looks there once more.
        original = language.original(name, year)
        if original:
            found = einthusan_source.find(name, year, prefer=original)
        return _store(imdb, found, original)
    finally:
        lock.release()


def prewarm(imdb, name, year):
    """Start the scan while the title page is being read.

    The frame asks for the same thing a click later; doing the work now is
    what turns a five-second wait into an instant one. On a host that freezes
    the process after the response, this is simply skipped.
    """
    if not (imdb or "").strip() or _row(imdb):
        return

    with _lock_guard:
        if _warmers[0] >= WARM_THREADS:
            return
        _warmers[0] += 1

    def work():
        try:
            # the same queue the route uses, so a burst of title pages cannot
            # turn into a burst of scans
            with limits.scan_slot():
                warm(imdb, name, year)
        except Exception:
            pass
        finally:
            with _lock_guard:
                _warmers[0] -= 1

    threading.Thread(target=work, name="einthusan-warm", daemon=True).start()
