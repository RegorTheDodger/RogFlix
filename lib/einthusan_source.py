"""
Einthusan as a source of its own, for Indian films.

The other players publish an embed URL that can be built from an id. Einthusan
does not: it signs an mp4 for one viewing, so the only way in is its own watch
page. This module bridges that — a film Cinemeta says is from India gets a
fifth button whose URL is a page on this site, and that page searches einthusan
by title and year, signs the file and plays it in the frame.

Searching is the part that is not free, so it happens when the frame is opened
rather than when the title page is drawn: the picker only asks `offers()`, which
reads the country Cinemeta already returned.
"""

import re
import threading
import time

from . import einthusan, language

# einthusan indexes eight Indian languages and carries nothing from outside
# India, so a film has to be Indian to be there at all.
INDIA = ("india",)

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


def is_indian(country):
    """Cinemeta writes country as "India" or "India, United States"."""
    for part in str(country or "").replace(";", ",").split(","):
        if part.strip().lower() in INDIA:
            return True
    return False


def offers(kind, country):
    """What the picker asks: films from India, and nothing else."""
    return kind == "movie" and is_indian(country)


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


def _matches(name, year):
    """{language: the einthusan record for this film in that index}, cached.

    Every index is asked because Cinemeta says a film is Indian but not which
    of the eight languages it is in, and a dub lives in its own index. Keeping
    each language's best entry — not just the closest overall — is what lets
    play() reach the index a film was made in even when a dub matched the
    title more closely.
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
    best, answered = {}, 0

    def scan(term):
        nonlocal answered
        for lang in einthusan.LANG_CODES:
            items = _page(term, lang)
            if items is None:
                continue
            answered += 1
            for item in items:
                score = _score(name, year_num, item)
                if score < GOOD_MATCH:
                    continue
                if lang not in best or score > best[lang][0]:
                    best[lang] = (score, item)

    scan(name.strip())
    # nothing close anywhere: ask once more under the title's first word, which
    # is how a catalogue title with a subtitle or a dash still finds its index
    # entry
    if not best:
        head = _first_word(name)
        if head:
            scan(head)

    matches = {lang: best[lang][1] for lang in einthusan.LANG_CODES
               if lang in best}
    if matches:
        with _lock:
            _found[key] = (now + HIT_TTL, matches)
        return matches

    # A title that really is not there is worth a short memory; a request that
    # never got through is asked again on the next visit, because the source
    # button is offered either way.
    if answered:
        with _lock:
            _found[key] = (now + MISS_TTL, None)
    return None


def find(name, year, prefer=""):
    """What einthusan has for a film, and which index to start on.

    Returns {"by_lang": {code: record}, "pick": code}, in einthusan's own
    language order, or None when no index has the film. `pick` is `prefer`
    when that index holds the film, otherwise whichever language matched the
    title most closely, ties going to the earlier language.
    """
    matches = _matches(name, year)
    if not matches:
        return None

    prefer = (prefer or "").strip().lower()
    if prefer in matches:
        pick = prefer
    else:
        year_num = _year(year)
        pick = max(matches,
                   key=lambda code: _score(name, year_num, matches[code]))
    return {"by_lang": matches, "pick": pick}


def play(name, year):
    """The one record the frame plays for a film, and the language it is in.

    Einthusan files a dub under an index of its own, so a film it carries in
    more than one language has several records, and the one matching the title
    best is as often a dub as the original. The frame plays the language the
    film was made in: the original index is asked of Wikipedia and taken when
    einthusan has it. A film einthusan carries only as a dub still plays, and
    the frame's badge says so.

    Returns {"record": item, "code": language code, "original": code or ""},
    or None when no index has the film.
    """
    have = find(name, year)
    if not have:
        return None
    original = language.original(name, year)
    code = original if original in have["by_lang"] else have["pick"]
    return {"record": have["by_lang"][code], "code": code,
            "original": original}


def stream(film_id):
    """The signed mp4 for one film, or None when einthusan has taken it down."""
    return einthusan.stream(film_id)
