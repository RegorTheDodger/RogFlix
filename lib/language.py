"""
The language a film was made in.

Cinemeta knows a film's country but not its language, so a South Asian film
that einthusan carries in several languages has no local way to say which
index is the original and which is a dub. Wikipedia writes it into the first
line of every film article ("RRR is a 2022 Indian Telugu-language epic ..."),
and its search API needs no key, so one search settles it.

Nothing here is load-bearing: a miss leaves the frame on the index that
matched the title best, and the language picker is always there to overrule
it.
"""

import json
import re
import threading
import time
import urllib.parse
import urllib.request

from . import einthusan

UA = "RogFlix/1.0 (+https://rogflix.vercel.app)"
API = "https://en.wikipedia.org/w/api.php"
TIMEOUT = 6

# The "-language" phrase is the convention every film article opens with, so
# matching it strictly beats reacting to a language mentioned in passing.
_PHRASE = re.compile(r"\b([A-Z][a-z]+)-language\b")
_TAGS = re.compile(r"<[^>]+>")
_PAREN = re.compile(r"\s*\((?:[^)]*film|soundtrack|disambiguation)\)\s*$", re.I)

# A film's language does not change, so the answer is worth a week. A miss is
# kept only briefly: an article may be written tomorrow, and a rate-limited
# request should be asked again later rather than never.
HIT_TTL = 7 * 24 * 3600
MISS_TTL = 900

_lock = threading.Lock()
_cache = {}


def _words(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()


def _year(value):
    try:
        return int(str(value if value is not None else "").strip()[:4])
    except (TypeError, ValueError):
        return 0


def _search(title, year):
    query = "%s %s film" % (title, year)
    url = ("%s?action=query&list=search&format=json&formatversion=2"
           "&srlimit=5&srsearch=%s" % (API, urllib.parse.quote(query)))
    request = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(2 * 1024 * 1024)
    data = json.loads(raw.decode("utf-8", "replace"))
    return (data.get("query") or {}).get("search") or []


def _is_the_film(page_title, title, snippet, year):
    """A result is about this film when the years agree and the article title
    is the film's title, not a song, a soundtrack or a similarly named film.

    The search is generous enough to return "Tumbbad (soundtrack)" first, and
    a soundtrack's language is still the film's, so only the year and the
    title have to line up — a mismatch here would otherwise pick a different
    film's language.
    """
    if str(year) not in snippet:
        return False
    page = " ".join(_words(_PAREN.sub("", page_title)))
    wanted = " ".join(_words(title))
    if not page or not wanted:
        return False
    if page == wanted or page.startswith(wanted):
        return True
    # a suffix the article adds ("Vikram" against "Vikram 2022"): every word of
    # the film's title has to appear in the article's
    return all(word in page.split() for word in wanted.split())


def original(title, year):
    """The language the film was made in, as einthusan's index code, or "".

    Only languages einthusan indexes are answered: the caller has nothing to
    do with "Bhojpuri", and an empty string simply means "no preference".
    """
    title = (title or "").strip()
    year_num = _year(year)
    if not title or not year_num:
        return ""

    key = "%s|%d" % (title.lower(), year_num)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now < hit[0]:
            return hit[1]

    answer = ""
    try:
        for result in _search(title, year_num):
            snippet = _TAGS.sub(" ", result.get("snippet") or "")
            if not _is_the_film(result.get("title") or "", title, snippet, year_num):
                continue
            phrase = _PHRASE.search(snippet)
            if phrase:
                code = phrase.group(1).lower()
                answer = code if code in einthusan.LANG_CODES else ""
            # the first article about this film decides, whether or not its
            # language is one einthusan carries
            break
    except Exception:
        # offline, throttled, or a changed API: no preference, and ask again
        # in a little while instead of caching the failure for a week
        with _lock:
            _cache[key] = (now + MISS_TTL, "")
        return ""

    with _lock:
        _cache[key] = (now + (HIT_TTL if answer else MISS_TTL), answer)
    return answer
