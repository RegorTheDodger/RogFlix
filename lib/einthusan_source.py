"""
Einthusan as a source of its own, for South Asian films.

The other players publish an embed URL that can be built from an id. Einthusan
does not: it signs an mp4 for one viewing, so the only way in is its own watch
page. This module bridges that — a film Cinemeta says is from South Asia gets a
fifth button whose URL is a page on this site, and that page searches einthusan
by title and year, signs the file and plays it in the frame.

Searching is the part that is not free, so it happens when the frame is opened
rather than when the title page is drawn: the picker only asks `offers()`, which
reads the country Cinemeta already returned.
"""

import re
import threading
import time

from . import einthusan

# Countries einthusan draws its eight languages from.
SOUTH_ASIAN = ("india", "pakistan", "bangladesh", "sri lanka", "nepal",
               "bhutan", "afghanistan", "maldives")

# A candidate has to be this close to the title, after the year penalty below.
GOOD_MATCH = 0.8

# einthusan is read as HTML, so a search is a handful of page fetches. A film
# found once is kept for the life of its signature; a miss is kept briefly, so
# a film added to the catalogue today shows up later without a restart.
HIT_TTL = 6 * 3600
MISS_TTL = 1800

# One index page per language, asked one at a time. Eight at once is fast when
# it works, but einthusan answers a burst with thin pages that parse to
# nothing, and a source that silently finds no film is worse than one that
# takes a few seconds. Two attempts per page covers a dropped connection.
PAGE_ATTEMPTS = 2
PAGE_TIMEOUT = 10

_lock = threading.Lock()
_found = {}


def is_south_asian(country):
    """Cinemeta writes country as "India" or "India, United States"."""
    for part in str(country or "").replace(";", ",").split(","):
        if part.strip().lower() in SOUTH_ASIAN:
            return True
    return False


def offers(kind, country):
    """What the picker asks: films from South Asia, and nothing else."""
    return kind == "movie" and is_south_asian(country)


def player_path(imdb_id):
    """The page here that resolves and plays the film."""
    return "/einthusan/%s" % imdb_id


def _year(value):
    try:
        return int(str(value if value is not None else "").strip()[:4])
    except (TypeError, ValueError):
        return 0


def _score(name, year, item):
    """Title closeness, with a film from another year pushed down.

    A remake shares its title with the original, so the year is what tells
    them apart; one year of slack covers a December release catalogued under
    the following year.
    """
    close = einthusan.similarity(name, item.get("title") or "")
    got = _year(item.get("year"))
    if year and got:
        gap = abs(got - year)
        if gap > 1:
            return 0.0
        return close - 0.05 * gap
    return close - 0.1


def _page(term, lang):
    """One page of a language index: [] for no matches, None for no answer.

    The two are different: "not there" is worth remembering for a while, a
    dropped request is not.
    """
    try:
        got = einthusan.fetch_prefix_page(term, lang, 1,
                                          attempts=PAGE_ATTEMPTS,
                                          timeout=PAGE_TIMEOUT)
    except Exception:
        return None
    return got[0] if got else []


def _first_word(name):
    """The prefix a shortened second pass asks for.

    einthusan indexes from the first letter of the title, so a longer title
    that is catalogued under a shorter one ("Kalki 2898 AD" for "Kalki
    2898-AD") is reached by asking for its first word.
    """
    words = re.split(r"[^A-Za-z0-9]+", (name or "").strip())
    head = words[0] if words else ""
    return head if head and head != (name or "").strip() else ""


def find(name, year):
    """The einthusan record for a film, or None. Cached, misses included.

    Every language index is searched at once: Cinemeta says a film is Indian
    but not which of the eight it is in, and a dub lives in its own index. The
    languages are also the tie-break — a film listed in both Tamil and Hindi
    keeps the Tamil one, because that is the original and einthusan lists it
    first.
    """
    if not (name or "").strip():
        return None

    key = ("%s|%s" % (name, year)).strip().lower()
    now = time.time()
    with _lock:
        hit = _found.get(key)
        if hit and now < hit[0]:
            return hit[1]

    year_num = _year(year)
    best, best_score, seen, answered = None, 0.0, set(), 0

    def scan(term):
        nonlocal best, best_score, answered
        for lang in einthusan.LANG_CODES:
            items = _page(term, lang)
            if items is None:
                continue
            answered += 1
            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                score = _score(name, year_num, item)
                # strict on purpose: the first language to reach a score owns
                # the tie
                if score > best_score:
                    best, best_score = item, score

    scan(name.strip())
    # nothing close: ask once more under the title's first word, which is how
    # a catalogue title with a subtitle or a dash still finds its index entry
    if not (best and best_score >= GOOD_MATCH):
        head = _first_word(name)
        if head:
            scan(head)

    if best and best_score >= GOOD_MATCH:
        with _lock:
            _found[key] = (now + HIT_TTL, best)
        return best

    # A title that really is not there is worth a short memory; a request that
    # never got through is asked again on the next visit, because the source
    # button is offered either way.
    if answered:
        with _lock:
            _found[key] = (now + MISS_TTL, None)
    return None


def stream(film_id):
    """The signed mp4 for one film, or None when einthusan has taken it down."""
    return einthusan.stream(film_id)
