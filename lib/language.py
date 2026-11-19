"""
The language a film was made in.

Cinemeta knows a film's country but not its language, and einthusan never says
whether an index entry is the original or a dub, so an Indian film that
einthusan carries in several languages has no local way to say which one to
start on. Wikipedia's film infobox states it as a field ("language = Telugu"),
and the first sentence of the article repeats it, so one search and one page
read settle it — no key, no dependency.

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

# The infobox field is the structured statement. The lead sentence is the
# fallback for an article whose infobox is built by a template, and it is the
# convention the language is written into ("a 2022 Indian Telugu-language film").
_FIELD = re.compile(r"\|\s*(?:language|lang)\s*=\s*([^\n]*)")
_PHRASE = re.compile(r"\b(Tamil|Telugu|Hindi|Malayalam|Kannada|Bengali|"
                     r"Marathi|Punjabi)-language\b", re.I)

# A search for a film also returns its soundtrack, its score and a novel of
# the same name; none of those states the film's language in an infobox.
_NOT_THE_FILM = re.compile(r"\([^)]*(?:soundtrack|album|score|song|music|"
                           r"novel|book|disambiguation)[^)]*\)", re.I)

# Infobox values carry markup: a citation, a language template, a link.
_REF = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.S | re.I)
# Keep what a template holds: a language list is written as {{ubl|Hindi|Marathi}}
# and dropping the braces' contents would drop the answer with it.
_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_TAG = re.compile(r"<[^>]+>")

# A film's language does not change, so the answer is worth a week. A miss is
# kept only briefly: an article may be written tomorrow, and a rate-limited
# request should be asked again later rather than never.
HIT_TTL = 7 * 24 * 3600
MISS_TTL = 900

_lock = threading.Lock()
_cache = {}


def _get(params):
    url = "%s?%s" % (API, urllib.parse.urlencode(params))
    request = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(4 * 1024 * 1024)
    return json.loads(raw.decode("utf-8", "replace"))


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _year(value):
    try:
        return int(str(value if value is not None else "").strip()[:4])
    except (TypeError, ValueError):
        return 0


def _clean(wikitext):
    text = _REF.sub(" ", wikitext or "")
    text = _TEMPLATE.sub(r" \1 ", text)
    text = _LINK.sub(r"\1", text)
    text = _TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_language(text):
    """The first word of the text that names an index einthusan has."""
    for word in re.findall(r"[A-Za-z]+", text or ""):
        if word.lower() in einthusan.LANG_CODES:
            return word.lower()
    return ""


def _page_title(title, year):
    """The article about this film.

    The search carries the year, so a remake's own article ranks first, and the
    result whose title is the film's own — with or without "(2022 film)" on it
    — wins. A near match is accepted only when one title starts the other,
    which is how a catalogue "Baahubali 2: The Conclusion" reaches the article
    of the same name.
    """
    data = _get({"action": "query", "list": "search", "format": "json",
                 "formatversion": "2", "srlimit": "6",
                 "srsearch": "%s %d film" % (title, year)})
    results = [result.get("title") or ""
               for result in (data.get("query") or {}).get("search") or []]
    results = [page for page in results if page and not _NOT_THE_FILM.search(page)]
    wanted = _norm(title)
    for page in results:
        plain = re.sub(r"\s*\([^)]*\)\s*$", "", page)
        if _norm(plain) == wanted:
            return page
    for page in results:
        plain = _norm(re.sub(r"\s*\([^)]*\)\s*$", "", page))
        if plain and (plain.startswith(wanted) or wanted.startswith(plain)):
            return page
    return ""


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
        page = _page_title(title, year_num)
        if page:
            data = _get({"action": "parse", "page": page, "prop": "wikitext",
                         "section": "0", "format": "json",
                         "formatversion": "2"})
            text = (data.get("parse") or {}).get("wikitext") or ""
            # the year has to be on the page as well, so a same-named film's
            # article cannot lend this one its language
            if str(year_num) in text:
                # citations carry their own |language=, so they are removed
                # before the infobox field is looked for
                field = _FIELD.search(_REF.sub(" ", text))
                if field:
                    answer = _first_language(_clean(field.group(1)))
                if not answer:
                    phrase = _PHRASE.search(_clean(text))
                    answer = phrase.group(1).lower() if phrase else ""
    except Exception:
        # offline, throttled, or a changed API: no preference, and ask again in
        # a little while instead of caching the failure for a week
        with _lock:
            _cache[key] = (now + MISS_TTL, "")
        return ""

    with _lock:
        _cache[key] = (now + (HIT_TTL if answer else MISS_TTL), answer)
    return answer
