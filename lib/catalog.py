"""
The Streaming Catalogs addon: thirty-five services, films and shows.

It answers catalogue requests only — no meta, no search — so a title's page is
built from Cinemeta and its playback from VidSpark. Every entry already carries
the poster, year and IMDb id a card needs, which is why the home page paints
without a hundred extra metadata calls.

Rows are fetched in parallel and cached for a quarter of an hour: the addon
serves around a quarter of a megabyte per catalogue.
"""

import json
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ADDON = (os.environ.get("CATALOG_ADDON")
         or "https://7a82163c306e-stremio-netflix-catalog-addon.baby-beamup.club/"
            "bmZ4LGRucCxoYm0sYW1wLGF0cCxwbXAscGNwLGhsdSxjcnUsbWdsLGN0cyxuZmss"
            "aGF5LGNsdixnb3AsamhzLHNzdCx2aWwsbmx6LHplZSxjcGQsc3R6LGRwZSxtYmks"
            "bXA5LHNvbnlsaXYsc2dvLHZpayxzaGQsYmJvLGFjdCxpdHYsaXFpLGNyYyxhbDQs"
            "YmJjLHNoYTo6OjE3OTQ2NTY4Mzg3MDU6MDowOkFV").rstrip("/")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

TTL = 900
TIMEOUT = 12

# The rows the home page opens with, in order. A service appears once: eight
# rails are enough for a first screen, and each one is somebody's starting
# point rather than a second Netflix shelf.
ROWS = [
    ("movie", "nfx", "Netflix"),
    ("movie", "amp", "Prime Video"),
    ("movie", "jhs", "JioHotstar"),
    ("series", "nfx", "Netflix series"),
    ("movie", "dnp", "Disney+"),
    ("movie", "hbm", "HBO Max"),
    ("series", "amp", "Prime Video series"),
    ("movie", "zee", "Zee5"),
]

_lock = threading.Lock()
_cache = {}

_YEAR = re.compile(r"(19|20)\d{2}")
_IMDB = re.compile(r"^tt\d+$")


def _get(url):
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and now < hit[0]:
            return hit[1]
    data = None
    try:
        request = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json,*/*;q=0.8",
        })
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read(8 * 1024 * 1024).decode("utf-8", "replace"))
    except Exception:
        data = None
    with _lock:
        _cache[url] = (now + (TTL if data is not None else 60), data)
    return data


def _year(raw):
    found = _YEAR.search(str(raw.get("year") or raw.get("released") or ""))
    return found.group(0) if found else ""


def _poster(url):
    """JustWatch serves 332px posters by default; 592 is the card size."""
    url = url or ""
    return url.replace("/s332/", "/s592/") if "/s332/" in url else url


def shape(raw, kind, service=""):
    imdb = (raw.get("imdb_id") or raw.get("id") or "").strip()
    if not _IMDB.match(imdb):
        return None
    return {
        "id": imdb,
        "type": "series" if (raw.get("type") or kind) == "series" else "movie",
        "name": raw.get("name") or "",
        "year": _year(raw),
        "cover": _poster(raw.get("poster")),
        "background": raw.get("background") or "",
        "description": raw.get("description") or "",
        "rating": raw.get("imdbRating") or "",
        "genres": raw.get("genre") or raw.get("genres") or [],
        "runtime": raw.get("runtime") or "",
        "service": service,
    }


def catalog(kind, catalog_id, service=""):
    url = "%s/catalog/%s/%s.json" % (ADDON, kind, catalog_id)
    metas = (_get(url) or {}).get("metas") or []
    return [item for item in (shape(raw, kind, service) for raw in metas) if item]


def rows(limit=16):
    """Eight rails, fetched at once; one slow service costs its own row."""
    out = []
    pool = ThreadPoolExecutor(max_workers=len(ROWS))
    try:
        jobs = [pool.submit(catalog, kind, cid, name)
                for kind, cid, name in ROWS]
        for (kind, cid, name), job in zip(ROWS, jobs):
            try:
                items = job.result(timeout=TIMEOUT + 2)
            except Exception:
                items = []
            if items:
                out.append((name, items[:limit]))
    finally:
        pool.shutdown(wait=False)
    return out


def featured(rows_data):
    for _name, items in rows_data:
        for item in items:
            if item.get("background") and item.get("rating"):
                return item
    return rows_data[0][1][0] if rows_data and rows_data[0][1] else None
