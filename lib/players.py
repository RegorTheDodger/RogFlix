"""
Playback through a chain of third-party players.

RogFlix streams from other people's frames: nothing is downloaded, converted
or proxied here, which is what makes the site behave the same on the Mac and
on Vercel. Each service below publishes an embed URL, and this module turns one
title into one URL per service, in the order the title page offers them:

    CineSrc     https://cinesrc.st/embed/movie/{tmdb}
                https://cinesrc.st/embed/tv/{tmdb}?s={season}&e={episode}
    VidLink     https://vidlink.pro/movie/{tmdb}
                https://vidlink.pro/tv/{tmdb}/{season}/{episode}
    VidSrc.sh   https://vidsrc.sh/embed/movie/{id}
                https://vidsrc.sh/embed/tv/{id}/{season}/{episode}
    VidSrc.mov  https://vidsrc.mov/embed/movie/{id}
                https://vidsrc.mov/embed/tv/{id}/{season}/{episode}
    Einthusan   /einthusan/{imdb}      Indian films only

CineSrc and VidLink are keyed by TMDB id only; the VidSrc pair takes a TMDB id
or an IMDb one, so a title Cinemeta knows without a `moviedb_id` still has a
player.

Einthusan signs an mp4 per viewing instead of publishing an embed URL, so that
last entry points at a page here (lib/einthusan_source.py resolves the film and
plays it). It is offered only for films whose country Cinemeta reports as
Indian: einthusan has no series and nothing from anywhere else, so the button
is left out rather than opening on an empty frame, and it can be pulled from
every title page by turning OFFER_EINTHUSAN below back to False.

One title rarely exists on every service, and any of them can fall over
mid-film, so the page shows the list and lets the viewer pick. The order here
is the order they are offered, best first.

Resume points belong to this site (localStorage, merged into the account).
Four players accept one in the URL — CineSrc and Einthusan as `t`, VidLink and
VidSrc.sh as `startAt` — and those open where the film was left; VidSrc.mov
documents no such parameter, so it starts at the top. VidLink, VidSrc.sh and
Einthusan also report playback back over postMessage (`PLAYER_EVENT`), which is
what keeps continue watching, watch time and finished state moving while any of
them is the source in use.
"""

import re
import urllib.parse

from . import einthusan_source

# --saffron in style.css. VidLink wants the hex without the "#", CineSrc with
# it. static/app.js replaces either with the accent picked on /settings.
ACCENT = "f2a33c"
ACCENT_HASH = "#" + ACCENT


def _tmdb_id(value):
    """TMDB ids are numeric. Cinemeta hands them over as an int or a string."""
    return re.sub(r"\D", "", str(value if value is not None else ""))


def _imdb_id(value):
    text = str(value if value is not None else "").strip()
    return text if re.match(r"^tt\d+$", text) else ""


def _either_id(tmdb, imdb):
    """What the services that accept both are given: TMDB when there is one."""
    return tmdb or imdb


def _cinesrc(kind, tmdb, imdb, season, episode):
    if not tmdb:
        return ""
    if kind == "series":
        if not season or not episode:
            return ""
        path = "/embed/tv/%s" % tmdb
        params = [("s", int(season)), ("e", int(episode))]
    else:
        path = "/embed/movie/%s" % tmdb
        params = []
    params.append(("color", ACCENT_HASH))
    # the player's own seek button, in seconds
    params.append(("seek", 10))
    # this site prints its own "resumed at" line, so the player's
    # Continue/Restart prompt would only ask the same question twice
    params.append(("continueprompt", "false"))
    return "https://cinesrc.st%s?%s" % (path, urllib.parse.urlencode(params))


def _vidlink(kind, tmdb, imdb, season, episode):
    if not tmdb:
        return ""
    params = [("primaryColor", ACCENT)]
    if kind == "series":
        if not season or not episode:
            return ""
        path = "/tv/%s/%d/%d" % (tmdb, int(season), int(episode))
        params.append(("nextbutton", "true"))
    else:
        path = "/movie/%s" % tmdb
    return "https://vidlink.pro%s?%s" % (path, urllib.parse.urlencode(params))


def _vidsrc(host, kind, tmdb, imdb, season, episode):
    title = _either_id(tmdb, imdb)
    if not title:
        return ""
    if kind == "series":
        if not season or not episode:
            return ""
        return "%s/embed/tv/%s/%d/%d" % (host, title, int(season), int(episode))
    return "%s/embed/movie/%s" % (host, title)


def _vidsrc_sh(kind, tmdb, imdb, season, episode):
    return _vidsrc("https://vidsrc.sh", kind, tmdb, imdb, season, episode)


def _vidsrc_mov(kind, tmdb, imdb, season, episode):
    return _vidsrc("https://vidsrc.mov", kind, tmdb, imdb, season, episode)


def _einthusan(kind, tmdb, imdb, season, episode):
    """No URL to build: the page resolves the film and signs the file."""
    return einthusan_source.player_path(imdb) if imdb else ""


def _indian_films(kind, country):
    return einthusan_source.offers(kind, country)


# Set this to False to take the fifth button off every Indian film while
# keeping the client, the source logic and the /einthusan route in the tree.
OFFER_EINTHUSAN = True

# Offered in this order. "resume" is the query parameter the player documents
# for a start second, or "" when it has none; static/app.js appends it. "gate"
# is what a title has to be for the source to be offered at all.
SOURCES = (
    {"key": "cinesrc", "name": "CineSrc", "origin": "https://cinesrc.st",
     "resume": "t", "build": _cinesrc},
    {"key": "vidlink", "name": "VidLink", "origin": "https://vidlink.pro",
     "resume": "startAt", "build": _vidlink},
    {"key": "vidsrc", "name": "VidSrc.sh", "origin": "https://vidsrc.sh",
     "resume": "startAt", "build": _vidsrc_sh},
    {"key": "vidsrc-mov", "name": "VidSrc.mov", "origin": "https://vidsrc.mov",
     "resume": "", "build": _vidsrc_mov},
    # last because it is the one source that has to be found before it plays
    {"key": "einthusan", "name": "Einthusan", "origin": "",
     "resume": "t", "build": _einthusan, "gate": _indian_films},
)


def offered_sources():
    """The entries currently on offer, which is SOURCES minus the switched-off
    ones. /api/status probes these, so a source that is not shown is not
    reported either."""
    return [source for source in SOURCES
            if source["key"] != "einthusan" or OFFER_EINTHUSAN]


def sources(kind, imdb_id, tmdb_id, season=0, episode=0, country=""):
    """Every player that can open this title, best first.

    A title with no id any of them understands gets an empty list, and the
    page says so rather than showing an empty frame. `country` is Cinemeta's,
    and only decides whether the India-only source is offered.
    """
    tmdb = _tmdb_id(tmdb_id)
    imdb = _imdb_id(imdb_id)
    out = []
    for source in offered_sources():
        gate = source.get("gate")
        if gate and not gate(kind, country):
            continue
        url = source["build"](kind, tmdb, imdb, season, episode)
        if not url:
            continue
        out.append({"key": source["key"], "name": source["name"],
                    "origin": source["origin"], "resume": source["resume"],
                    "url": url})
    return out


def embed_url(kind, imdb_id, tmdb_id, season=0, episode=0):
    """The first player's URL, or "" — what the page loads by default."""
    found = sources(kind, imdb_id, tmdb_id, season, episode)
    return found[0]["url"] if found else ""
