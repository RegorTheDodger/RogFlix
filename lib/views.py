"""
HTML rendering.

Catalogue rows come from the Streaming Catalogs addon; a title's page is built
from Cinemeta and its playback from the chain of players in lib/players.py.
Personal data remains in localStorage for offline browsing and is merged into
the account database when signed in.

Markup follows the class names in style.css. Rails are filled from app.js;
everything server-rendered is static HTML so the page paints without JS.
"""

import html
import re
import urllib.parse

from flask import request

from . import catalog
from . import players

NAV = [
    ("/", "Home", "home"),
    ("/search", "Search", "search"),
    ("/watchlist", "My List", "list"),
]




def esc(text):
    return html.escape(text or "", quote=True)


def origin():
    """Absolute base for the share card. Taken from the request so the tag is
    right on localhost, on Render and on Vercel without being hard-coded."""
    try:
        return request.host_url.rstrip("/")
    except RuntimeError:
        return ""


# --------------------------------------------------------------------------
# icons
# --------------------------------------------------------------------------

ICON_SEARCH = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
               ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
               ' aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
               '<path d="m20 20-3.5-3.5"/></svg>')

ICON_PLAY = ('<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"'
             ' aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>')

ICON_PAUSE = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"'
              ' aria-hidden="true"><rect x="7" y="5" width="3.4" height="14"'
              ' rx="1.1"/><rect x="13.6" y="5" width="3.4" height="14"'
              ' rx="1.1"/></svg>')

ICON_PLUS = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
             ' stroke="currentColor" stroke-width="2.2" stroke-linecap="round"'
             ' aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>')

ICON_CHECK = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
              ' stroke="currentColor" stroke-width="2.4" stroke-linecap="round"'
              ' stroke-linejoin="round" aria-hidden="true">'
              '<path d="m5 13 4 4L19 7"/></svg>')

ICON_PREV = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none"'
             ' stroke="currentColor" stroke-width="2.4" stroke-linecap="round"'
             ' stroke-linejoin="round" aria-hidden="true">'
             '<path d="m15 6-6 6 6 6"/></svg>')

ICON_NEXT = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none"'
             ' stroke="currentColor" stroke-width="2.4" stroke-linecap="round"'
             ' stroke-linejoin="round" aria-hidden="true">'
             '<path d="m9 6 6 6-6 6"/></svg>')

ICON_GEAR = ('<svg viewBox="0 0 24 24" width="19" height="19" fill="none"'
             ' stroke="currentColor" stroke-width="1.8" stroke-linecap="round"'
             ' stroke-linejoin="round" aria-hidden="true">'
             '<path d="M9.6 3.2h4.8l.7 2.1a7.3 7.3 0 0 1 1.7 1l2.1-.6 2.4 4.1-1.5 1.6'
             'a7.4 7.4 0 0 1 0 2l1.5 1.6-2.4 4.1-2.1-.6a7.3 7.3 0 0 1-1.7 1l-.7 2.1H9.6l-.7-2.1'
             'a7.3 7.3 0 0 1-1.7-1l-2.1.6-2.4-4.1 1.5-1.6a7.4 7.4 0 0 1 0-2L2.7 9.8l2.4-4.1 2.1.6'
             'a7.3 7.3 0 0 1 1.7-1z"/><circle cx="12" cy="12.4" r="2.7"/></svg>')

ICON_GITHUB = ('<svg viewBox="0 0 16 16" width="16" height="16"'
              ' aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29'
              ' 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94'
              '-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87'
              '.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15'
              '-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27'
              ' 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87'
              ' 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01'
              ' 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')

ICON_HOME = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
             ' stroke="currentColor" stroke-width="2" stroke-linejoin="round"'
             ' aria-hidden="true"><path d="m3 11 9-8 9 8v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
             '<path d="M9 21v-6h6v6"/></svg>')
ICON_LIST = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
             ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
             ' aria-hidden="true"><path d="M5 5h14M5 12h14M5 19h14"/></svg>')

ICON_LIB = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
            ' stroke-linejoin="round" aria-hidden="true">'
            '<rect x="3" y="4" width="7" height="7" rx="1.5"/>'
            '<rect x="14" y="4" width="7" height="7" rx="1.5"/>'
            '<rect x="3" y="15" width="7" height="7" rx="1.5"/>'
            '<rect x="14" y="15" width="7" height="7" rx="1.5"/></svg>')

NAV_ICONS = {"home": ICON_HOME, "search": ICON_SEARCH, "list": ICON_LIST,
             "lib": ICON_LIB}


# --------------------------------------------------------------------------
# shell
# --------------------------------------------------------------------------



def page(title, body, top_lang="english"):
    current = title.lower()
    links = "".join(
        '<a class="nav-link%s" href="%s">%s<span>%s</span></a>'
        % (" on" if (href == "/" and current == "home")
           or href.lstrip("/").lower() == current else "",
           href, NAV_ICONS[key], esc(label))
        for href, label, key in NAV)

    # The home page carries the site name; every other page leads with its own
    # name so a tab in a crowded strip still says which page it is.
    shown = ("RogFlix &middot; Every service, one shelf"
             if current == "home" else "%s &middot; RogFlix" % esc(title))

    return (
        '<!DOCTYPE html>'
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="dark">'
        '<meta name="theme-color" content="#0a0809">'
        '<script>try{document.documentElement.setAttribute("data-theme",'
        'localStorage.getItem("iml:theme")||"saffron")}catch(e){}</script>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,400..600'
        '&amp;family=IBM+Plex+Mono:wght@400;500'
        '&amp;family=Instrument+Sans:wght@400;500;600&amp;display=swap">'
        '<link rel="icon" href="/static/favicon-32.png" sizes="32x32"'
        ' type="image/png">'
        '<link rel="icon" href="/static/icon-192.png" sizes="192x192"'
        ' type="image/png">'
        '<link rel="apple-touch-icon" href="/static/logo-180.png">'
        '<link rel="manifest" href="/static/manifest.json">'
        '<meta name="application-name" content="RogFlix">'
        '<meta property="og:site_name" content="RogFlix">'
        '<meta property="og:title" content="%s">'
        '<meta property="og:image" content="%s/static/og.png">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="description" content="Tamil, Telugu, Malayalam, '
        'Kannada, Hindi and English films and shows.">'
        "<title>%s</title>"
        '<link rel="stylesheet" href="/static/style.css">'
        '<script defer src="https://cdn.vercel-insights.com/v1/script.js"></script>'
        "</head><body>"
        '<header class="nav" id="bar"><div class="nav-inner">'
        '<a class="brand" href="/" aria-label="RogFlix home">'
        '<img class="brand-mark" src="/static/mark.png" alt="" width="32"'
        ' height="28"><span class="brand-word">Rog<em>Flix</em></span>'
        '<span class="brand-tag">Every service</span></a>'
        '<nav class="nav-links">%s</nav>'
        '<form class="nav-search" action="/search" method="get" role="search">'
        '<span class="nav-field">%s'
        '<input type="search" name="q" placeholder="Search films and shows"'
        ' autocomplete="off" aria-label="Search films"></span>'
        "</form>"
        '<a class="nav-gear" href="/settings" aria-label="Settings">%s</a>'
        "</div></header>"
        '<main class="page" data-lang="en">%s</main>'
        '<script src="/static/motion.js"></script>'
        '<script src="/static/app.js?v=3"></script>'
        "</body></html>"
        % (shown, origin(), shown, links, ICON_SEARCH, ICON_GEAR, body)
    )


# --------------------------------------------------------------------------
# pieces
# --------------------------------------------------------------------------





def continue_head_actions():
    """Emptying the shelf at once, behind its own yes/no question."""
    return (
        '<button class="shelf-clear" type="button" data-action="clear-continue"'
        ' hidden>Clear all</button>'
        '<span class="shelf-confirm" data-confirm="continue" hidden>'
        "<span>Are you sure?</span>"
        '<button class="btn tiny" type="button"'
        ' data-action="confirm-clear-continue">Yes</button>'
        '<button class="btn ghost tiny" type="button"'
        ' data-action="cancel-clear-continue">No</button></span>'
    )


def shelf(title, shelf_id, items_html="", empty_text="", note="",
          head_extra=""):
    head = '<h2>%s</h2>' % esc(title)
    if note:
        head += '<p class="shelf-note">%s</p>' % esc(note)
    head += head_extra
    return (
        '<section class="shelf" data-row="%s">'
        '<div class="shelf-head">%s</div>'
        '<div class="rail-wrap">'
        '<div class="rail" data-shelf="%s" tabindex="0" aria-label="%s">%s</div>'
        '<button class="rail-btn prev" data-scroll="-1" tabindex="-1"'
        ' aria-label="Scroll left">%s</button>'
        '<button class="rail-btn next" data-scroll="1" tabindex="-1"'
        ' aria-label="Scroll right">%s</button>'
        "</div>"
        '<p class="empty" data-empty="%s"%s>%s</p>'
        "</section>"
        % (esc(shelf_id), head, esc(shelf_id), esc(title), items_html,
           ICON_PREV, ICON_NEXT, esc(shelf_id),
           "" if empty_text else " hidden", esc(empty_text))
    )


def grid(items_html, empty_text=""):
    return (
        '<div class="grid">%s</div>'
        '<p class="empty"%s>%s</p>'
        % (items_html, "" if empty_text else " hidden", esc(empty_text))
    )


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------








def watchlist_page(top_lang="english"):
    """Films and shows kept apart: they are browsed differently and a list of
    both mixes a two-hour film in with a five-season show."""

    def collection(name, title, empty_text):
        return (
            '<section class="collection" data-collection="%s">'
            '<div class="collection-head">'
            '<h2>%s</h2>'
            '<p class="shelf-note" data-count="%s"></p></div>'
            '<div class="grid" data-shelf="%s"></div>'
            '<p class="empty" data-empty="%s" hidden>%s</p>'
            "</section>" % (name, esc(title), name, name, name, esc(empty_text))
        )

    return ("My List",
            '<section class="page-head">'
            '<p class="eyebrow">Saved</p>'
            '<h1 class="h1">My list</h1>'
            '<p class="lede">Films and shows you kept. Stored in this browser, '
            "and carried to your other devices when you are signed in.</p>"
            '<p class="head-actions">'
            '<button class="btn ghost" type="button" data-action="clear-watchlist">'
            "Clear list</button></p></section>"
            + collection("films", "Films", "Nothing saved yet.")
            + collection("shows", "TV shows", "Nothing saved yet."),
            top_lang)



# --------------------------------------------------------------------------
# library (Cinemeta for metadata, a chosen player for playback)
# --------------------------------------------------------------------------


def library_card(item):
    """A Cinemeta title. It links to its own page, not to a player, because
    a source has to be chosen first."""
    kind = "series" if item.get("type") == "series" else "movie"
    href = "/title/%s/%s" % (kind, esc(item["id"]))
    ext_id = "ext:%s:%s" % (kind, item["id"])
    # Cinemeta calls it a poster, the catalogue a cover: accept either
    cover = item.get("poster") or item.get("cover") or ""
    poster = ('<img loading="lazy" src="%s" alt="">' % esc(cover)
              if cover else '<span class="card-none">No artwork</span>')

    bits = [item.get("year")]
    if item.get("rating"):
        bits.append("%s/10" % item["rating"])
    meta = " &middot; ".join(esc(bit) for bit in bits if bit)

    return (
        '<article class="card" data-id="%s" data-title="%s" data-cover="%s"'
        ' data-url="%s" data-href="%s" data-year="%s" data-lang="English">'
        '<a class="card-link" href="%s" aria-label="%s">'
        '<span class="card-poster">%s'
        '<span class="card-shade"></span><span class="card-play">%s</span>'
        "</span>"
        '<span class="card-text"><b>%s</b>%s</span></a>'
        '<button class="card-add" type="button" data-action="toggle"'
        ' aria-label="Add to my list"><span class="add-off">%s</span>'
        '<span class="add-on">%s</span></button></article>'
        % (esc(ext_id), esc(item.get("name")), esc(cover), esc(href), esc(href),
           esc(item.get("year") or ""), href, esc(item.get("name") or ""),
           poster, ICON_PLAY, esc(item.get("name") or ""),
           ('<em>%s</em>' % meta) if meta else "", ICON_PLUS, ICON_CHECK))


def library_field(value=""):
    return (
        '<form class="search-field sf-center" action="/search"'
        ' method="get" role="search">'
        '<span class="sf-input">%s<input type="search" name="q" value="%s"'
        ' placeholder="Search movies and shows" autocomplete="off"'
        ' aria-label="Search the library" required></span>'
        '<button class="btn" type="submit">Search</button></form>'
        % (ICON_SEARCH, esc(value)))



def _progress_id(kind, media_id, season, episode):
    """What continue-watching counts as one thing: a film, or one episode."""
    base = "ext:%s:%s" % (kind, media_id)
    if kind == "series":
        return "%s:%d:%d" % (base, season, episode)
    return base


def _runtime_seconds(value):
    """Cinemeta writes runtimes as "22 min" or "1h 22min"; seconds please."""
    text = str(value or "").lower()
    hours = re.search(r"(\d+)\s*h", text)
    minutes = re.search(r"(\d+)\s*m", text)
    total = (int(hours.group(1)) * 3600 if hours else 0) + \
            (int(minutes.group(1)) * 60 if minutes else 0)
    if not total:
        plain = re.match(r"^\s*(\d+)\s*$", text)
        total = int(plain.group(1)) * 60 if plain else 0
    return total


def title_page(item, season=1, episode=1, seasons=(), by_season=None):
    """One film or one episode: the player first, every known fact beneath it.

    Cinemeta is the only source here — backdrop, poster, year, runtime, rating,
    genres, synopsis, cast, crew, awards, links and the episode list all come
    from it, so a film and a show are laid out the same way.
    """
    kind = "series" if item.get("type") == "series" else "movie"
    href = "/title/%s/%s" % (kind, item["id"])
    # what continue-watching reopens: one episode, not just the show
    entry_href = ("%s?s=%d&e=%d" % (href, season, episode)
                  if kind == "series" else href)
    progress_id = _progress_id(kind, item["id"], season, episode)
    seasons = list(seasons) or [1]
    by_season = by_season or {}
    poster = item.get("poster") or ""
    background = item.get("background") or poster

    # The list saves a show, not the episode somebody happens to be on: adding
    # Game of Thrones from S04E02 puts Game of Thrones in My List. Resume
    # positions stay per episode, so continue watching can still reopen it.
    list_id = "ext:series:%s" % item["id"] if kind == "series" else progress_id

    body = ['<article class="title" data-id="%s" data-title="%s"'
            ' data-media="%s" data-kind="%s"'
            ' data-cover="%s" data-url="%s" data-href="%s" data-year="%s"'
            ' data-runtime="%d" data-lang="English"'
            ' data-list-id="%s" data-list-href="%s">'
            % (esc(progress_id), esc(item.get("name")), esc(item["id"]), kind,
               esc(poster), esc(href), esc(entry_href),
               esc(item.get("year") or ""),
               _runtime_seconds(item.get("runtime")), esc(list_id), esc(href))]

    # ---------------------------------------------------------------- stage
    # The frame is the page. Nothing is stacked above it but the navigation
    # bar, so a click on a card lands on the film rather than on a poster.

    body.append('<section class="stage">')
    if background:
        body.append('<div class="stage-art"><img src="%s" alt=""></div>'
                    % esc(background))
    body.append('<div class="stage-scrim"></div><div class="stage-inner">')

    # Playback is somebody else's player in a frame. Nothing is downloaded,
    # converted or proxied here, which is what makes this work on Vercel too.
    # One title is rarely on every service, so the first player loads and the
    # rest sit under it as a picker.
    found = players.sources(kind, item.get("id"), item.get("tmdb"), season,
                            episode, item.get("country"))
    if found:
        first = found[0]
        where = ("Season %d, episode %d" % (season, episode)
                 if kind == "series" else "This film")
        # The frame takes a moment to paint, which reads as a broken player.
        # A poster cover keeps the stage dark until it is asked for.
        gate = (
            '<button class="gate" type="button" data-action="reveal-embed">'
            '<img class="gate-art" src="%s" alt="">'
            '<span class="gate-play">%s<span>Play</span></span>'
            "</button>" % (esc(poster or background), ICON_PLAY)
            if (poster or background) else "")
        # static/app.js loads whichever button is on, so each one carries the
        # URL its own player understands, plus the start-second parameter it
        # documents (empty for the players that have none).
        pickers = "".join(
            '<button class="source-btn%s" type="button" data-source="%s"'
            ' data-src="%s" data-origin="%s" data-resume="%s"'
            ' aria-pressed="%s">%s</button>'
            % (" on" if index == 0 else "", esc(one["key"]), esc(one["url"]),
               esc(one["origin"]), esc(one["resume"]),
               "true" if index == 0 else "false", esc(one["name"]))
            for index, one in enumerate(found))
        body.append(
            '<div class="player-wrap"><div class="player embed">'
            '<iframe id="player" src="%s" data-player="%s" allowfullscreen'
            ' allow="autoplay; fullscreen; encrypted-media; picture-in-picture"'
            ' loading="eager" title="%s">'
            '</iframe>%s</div></div>'
            '<div class="stage-under">'
            '<div class="sources" role="group" aria-label="Playback source">'
            '<span class="sources-label">Source</span>%s</div>'
            '<p class="resume" data-role="resume"></p>'
            '<p class="play-hint" data-role="stuck" hidden>Nothing has loaded'
            ' yet — give it a moment, or pick another source above.</p>'
            '<p class="play-note">%s from <b data-role="source-name">%s</b>.'
            ' If the frame stays blank, pick another source — they carry'
            ' different copies of the same title. <a href="%s"'
            ' data-embed-link target="_blank" rel="noopener noreferrer">'
            'Open in a new tab</a> if this one will not play.</p></div>'
            % (esc(first["url"]), esc(first["key"]), esc(where), gate,
               pickers, esc(where), esc(first["name"]), esc(first["url"])))
    else:
        body.append('<p class="play-note">No player for this title: Cinemeta '
                    'did not return an id any of the players key on.</p>')
    body.append('</div></section>')

    # What to watch once this one ends: the next episode, or the shelf it came
    # from. static/app.js fills this in when a player reports the end.
    body.append('<section class="up-next" data-role="up-next" hidden>'
                '<div class="up-next-head"><h2>Up next</h2>'
                '<p data-role="up-next-note"></p></div>'
                '<div class="up-next-row" data-role="up-next-row"></div>'
                '</section>')

    # ---------------------------------------------------------------- sheet
    # Everything Cinemeta knows, underneath the frame: the poster, title, blurb
    # and people on the left; the numbers and the buttons on the right, starting
    # level with the title so the two columns read as one row.

    body.append('<section class="sheet"><div class="sheet-cols">')

    body.append('<div class="sheet-main"><div class="sheet-head">')
    if poster:
        body.append('<div class="sheet-poster"><img src="%s" alt=""></div>'
                    % esc(poster))
    body.append('<div class="sheet-id">')
    eyebrow = "Series" if kind == "series" else "Film"
    if kind == "series":
        eyebrow += (" &middot; Season %d &middot; Episode %d"
                    % (season, episode))
    body.append('<p class="eyebrow">%s</p>' % eyebrow)
    body.append('<h1 class="display">%s</h1>' % esc(item.get("name")))
    body.append('</div></div>')

    if item.get("description"):
        body.append('<p class="synopsis">%s</p>' % esc(item["description"]))

    rows = []
    if item.get("directors"):
        rows.append(("Director", esc(", ".join(item["directors"]))))
    if item.get("writers"):
        rows.append(("Written by", esc(", ".join(item["writers"]))))
    cast = [name for name in (item.get("cast") or [])[:10] if name]
    if cast:
        rows.append(("Cast", esc(", ".join(cast))))
    if item.get("country"):
        rows.append(("Country", esc(item["country"])))
    if item.get("awards"):
        rows.append(("Awards", esc(item["awards"])))
    if rows:
        body.append('<dl class="facts">%s</dl>'
                    % "".join("<dt>%s</dt><dd>%s</dd>" % (esc(key), value)
                              for key, value in rows))
    body.append('</div>')

    body.append('<div class="sheet-side"><h2 class="side-head">Details</h2>')
    details = []
    if item.get("year"):
        details.append(("Year", esc(item["year"])))
    if item.get("runtime"):
        details.append(("Runtime", esc(item["runtime"])))
    if item.get("rating"):
        details.append(("Rating", esc("%s/10 on IMDb" % item["rating"])))
    if item.get("status"):
        details.append(("Status", esc(item["status"])))
    if item.get("released"):
        details.append(("Released", esc(item["released"])))
    if details:
        body.append('<dl class="facts side-facts">%s</dl>'
                    % "".join("<dt>%s</dt><dd>%s</dd>" % (esc(key), value)
                              for key, value in details))

    genre_html = "".join(
        '<a class="chip" href="/search?q=%s">%s</a>'
        % (esc(urllib.parse.quote(genre)), esc(genre))
        for genre in (item.get("genres") or [])[:6])
    if genre_html:
        body.append('<div class="tag-row">%s</div>' % genre_html)

    body.append('<div class="sheet-actions">'
                '<button class="btn ghost watch-add" type="button"'
                ' data-action="toggle"><span class="add-off">%s'
                '<span>My List</span></span><span class="add-on">%s'
                '<span>In My List</span></span></button>' % (ICON_PLUS, ICON_CHECK))
    if item.get("trailer"):
        body.append('<a class="btn ghost" href="https://www.youtube.com/watch?v=%s"'
                    ' target="_blank" rel="noopener noreferrer">Trailer</a>'
                    % esc(item["trailer"]))
    if item.get("imdb"):
        body.append('<a class="btn ghost" href="%s" target="_blank"'
                    ' rel="noopener noreferrer">IMDb page</a>' % esc(item["imdb"]))
    body.append('</div></div></div>')

    body.append('<p class="title-foot">Every detail on this page comes from '
                'Cinemeta &middot; playback runs in the player you pick.</p>')
    body.append('</section>')

    # ------------------------------------------------------------- episodes

    if kind == "series" and by_season:
        # every season is rendered once: switching is a class change in
        # app.js instead of a round trip through the server
        tabs = "".join(
            '<a class="season-tab%s" href="%s?s=%d" data-season-tab="%d">'
            'Season %d</a>'
            % (" on" if value == season else "", esc(href), value, value, value)
            for value in seasons)
        groups, total = [], 0
        for value in seasons:
            entries = by_season.get(value) or []
            total += len(entries)
            cards = []
            for entry in entries:
                thumb = ('<img loading="lazy" src="%s" alt="">'
                         % esc(entry["thumbnail"])) if entry.get("thumbnail") else ""
                overview = ('<span class="ep-overview">%s</span>'
                            % esc(entry["overview"])) if entry.get("overview") else ""
                on = value == season and entry["episode"] == episode
                cards.append(
                    '<a class="episode%s" href="%s?s=%d&amp;e=%d"'
                    ' data-season="%d" data-episode="%d">'
                    '<span class="ep-thumb">%s</span>'
                    '<span class="ep-body"><span class="ep-no">S%02d E%02d</span>'
                    '<b class="ep-name">%s</b>%s</span></a>'
                    % (" on" if on else "", esc(href), value, entry["episode"],
                       value, entry["episode"], thumb, value, entry["episode"],
                       esc(entry.get("name")
                           or "Episode %d" % entry["episode"]), overview))
            groups.append('<div class="episodes" data-season-group="%d"%s>%s</div>'
                          % (value, "" if value == season else " hidden",
                             "".join(cards)))
        body.append('<section class="tv"><div class="shelf-head">'
                    '<h2>Episodes</h2><p class="shelf-note" data-ep-count>%d '
                    'episodes &middot; Season %d</p></div>'
                    '<div class="seasons">%s</div>%s</section>'
                    % (total, season, tabs, "".join(groups)))

    body.append('</article>')
    return (item.get("name") or "Title", "".join(body), "english")


# --------------------------------------------------------------------------
# einthusan frame
# --------------------------------------------------------------------------

# The one player that is not somebody else's page. It is a document of its own
# because it fills an iframe rather than a window, so it carries none of the
# site's navigation — just the film, and a badge that fades once it starts.
EINTHUSAN_CSS = (
    "html,body{margin:0;height:100%;background:#000;color:#f3ece4;"
    "font:14px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
    "video{display:block;width:100%;height:100%;background:#000}"
    ".badge{position:fixed;left:14px;top:12px;margin:0;padding:6px 11px;"
    "border-radius:999px;background:rgba(0,0,0,.6);font-size:11px;"
    "letter-spacing:.08em;text-transform:uppercase;opacity:.92;"
    "transition:opacity .6s ease;pointer-events:none;max-width:44%;"
    "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    ".badge.gone{opacity:0}"
    ".say{position:fixed;inset:0;display:flex;flex-direction:column;"
    "align-items:center;justify-content:center;gap:8px;text-align:center;"
    "padding:24px}"
    ".say h1{margin:0;font:600 20px/1.3 Georgia,serif}"
    ".say p{margin:0;max-width:34em;color:#b8ada1;line-height:1.5}"
    ".say .kicker{margin:0 0 2px;font-size:11px;letter-spacing:.14em;"
    "text-transform:uppercase;color:#f2a33c}"
    "[hidden]{display:none!important}"
)


def _standalone(head_html, css, body):
    """A complete document for a frame. Callers pass escaped text."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="dark">'
        '<meta name="theme-color" content="#000000">'
        '<meta name="robots" content="noindex">'
        "<title>%s</title><style>%s</style></head><body>%s</body></html>"
        % (head_html, css, body))


def einthusan_player(title, media_id, start=0):
    """The frame for an Indian film: a page that paints at once.

    Einthusan is the only source with no embed URL of its own, and finding a
    film there means reading pages until its index answers, so the resolution
    cannot happen before the title page is drawn or as part of it. This shell
    appears immediately saying what it is doing; /api/einthusan/<id> does the
    work and answers with the signed mp4, and the script below plays it with
    the site's resume and the same PLAYER_EVENT reports the other players send.

    Einthusan files a dub under an index of its own, so a film it carries in
    more than one language has a different record per language. The frame
    plays the one the film was made in and offers no choice: the API takes
    that index and hands over the single stream einthusan signs for it. The
    badge names the language playing, and says when the only copy einthusan
    has is a dub.
    """
    start = max(0, int(start or 0))
    badge = "Einthusan"
    if start:
        badge += " &middot; resumed at %d:%02d" % (start // 60, start % 60)
    script = """
<script>
var video = document.getElementById('film'),
    badge = document.getElementById('badge'),
    say = document.getElementById('say'),
    head = document.getElementById('say-head'),
    body = document.getElementById('say-body'),
    start = __START__,
    media = '__MEDIA__',
    resumeAt = start;

function report(status) {
  try {
    window.parent.postMessage({type: 'PLAYER_EVENT', data: {
      player_status: status,
      player_progress: video.currentTime || 0,
      player_duration: video.duration || 0
    }}, '*');
  } catch (e) {}
}

function fail(message) {
  head.textContent = 'Not on Einthusan';
  body.textContent = message + ' Pick another source under the frame — '
    + 'they carry different copies of the same film.';
}

function clock(seconds) {
  var m = Math.floor(seconds / 60), r = Math.floor(seconds % 60);
  return m + ':' + (r < 10 ? '0' : '') + r;
}

/* Whether the language playing is the one the film was made in. The answer is
   empty when nothing knows it, and then the badge only names the language. */
function mark(data) {
  if (!data.original || !data.language_code) return '';
  return data.original === data.language_code ? ' · original' : ' · dub';
}

function load(at) {
  fetch('/api/einthusan/' + media, {credentials: 'same-origin'})
    .then(function (response) { return response.json(); })
    .then(function (data) {
      if (!data || !data.url) {
        fail((data && data.error) || 'No playable copy of this film right now.');
        return;
      }
      resumeAt = at;
      badge.className = 'badge';
      badge.textContent = 'Einthusan' + (data.language ? ' · ' + data.language : '')
        + mark(data) + (start ? ' · resumed at ' + clock(start) : '');
      video.src = data.url;
      video.hidden = false;
      say.hidden = true;
      video.load();
    })
    .catch(function () {
      fail('Einthusan could not be reached just now.');
    });
}

video.addEventListener('loadedmetadata', function () {
  var to = resumeAt;
  resumeAt = 0;
  if (to > 0 && (!video.duration || to < video.duration - 5)) {
    try { video.currentTime = to; } catch (e) {}
  }
});
video.addEventListener('play', function () {
  setTimeout(function () { badge.className = 'badge gone'; }, 4000);
  report('playing');
});
var last = 0;
video.addEventListener('timeupdate', function () {
  var now = Date.now();
  if (now - last < 5000) return;
  last = now;
  report('playing');
});
video.addEventListener('seeked', function () { report('seeked'); });
video.addEventListener('pause', function () { report('paused'); });
video.addEventListener('ended', function () { report('completed'); });

load(start);
</script>"""
    script = (script.replace("__START__", str(start))
                    .replace("__MEDIA__", esc(media_id)))
    body = (
        "<video id='film' controls playsinline preload='metadata' hidden></video>"
        '<p class="badge" id="badge">%s</p>'
        '<div class="say" id="say"><p class="kicker">Einthusan</p>'
        '<h1 id="say-head">Finding this film</h1>'
        '<p id="say-body">Einthusan indexes eight languages, so this can take '
        "a moment.</p></div>%s" % (badge, script))
    return _standalone("%s &middot; Einthusan" % esc(title or "Film"),
                       EINTHUSAN_CSS, body)


def einthusan_missing(title, reason=""):
    """Einthusan did not have it: say so where the film would have been."""
    why = reason or ("Einthusan has no playable copy of&quot;%s&quot; right now."
                     % esc(title or "this film"))
    body = (
        '<div class="say"><p class="kicker">Einthusan</p>'
        "<h1>Not on Einthusan</h1>"
        "<p>%s</p><p>Pick another source under the frame — they carry "
        "different copies of the same film.</p></div>" % why)
    return _standalone("%s &middot; Einthusan" % esc(title or "Film"),
                       EINTHUSAN_CSS, body)


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------

def billboard_fallback():
    return (
        '<section class="bb bb-plain"><div class="bb-inner">'
        '<p class="bb-kicker">RogFlix</p>'
        '<h1 class="bb-title">Every service.<br>One shelf.</h1>'
        '<p class="bb-sub">Search a title, or start with a row below.</p>'
        '<div class="bb-search">%s</div></div></section>' % library_field()
    )


def billboard_slide(item, index, row_id=""):
    """One film of the hero carousel.

    Only the first slide carries image URLs; the rest load theirs when they
    come round, so the home page is not ten backdrops heavier than before.
    The row id is kept on the slide so a hidden catalogue can drop its films.
    """
    live = index == 0
    cover = item.get("background") or item.get("cover") or ""
    poster = item.get("cover") or ""
    kind = "series" if item.get("type") == "series" else "movie"
    href = "/title/%s/%s" % (kind, item["id"])
    bits = (item.get("service"), "Film", item.get("year"))
    chips = "".join('<span class="bb-chip">%s</span>' % esc(bit)
                    for bit in bits if bit)

    def art(url, css_class):
        if not url:
            return ""
        source = ('src="%s"' if live else 'data-src="%s"') % esc(url)
        return ('<div class="%s" aria-hidden="true"><img %s alt=""></div>'
                % (css_class, source))

    return (
        '<section class="bb%s" data-slide="%d" data-row="%s">'
        '%s<div class="bb-scrim" aria-hidden="true"></div>'
        '<div class="bb-inner">'
        '<p class="bb-kicker">Featured</p>'
        '<h1 class="bb-title">%s</h1>%s'
        '<div class="bb-actions">'
        '<a class="btn play" href="%s">%sPlay</a>'
        '<a class="btn ghost" href="%s">More info</a>'
        '</div></div>%s</section>'
        % (" is-live" if live else "", index, esc(row_id),
           art(cover, "bb-art"),
           esc(item.get("name") or ""),
           '<p class="bb-meta">%s</p>' % chips if chips else "",
           esc(href), ICON_PLAY, esc(href), art(poster, "bb-poster")))


def billboard_carousel(picks):
    """The home hero: the films from the rails, one at a time.

    The dots and the countdown bar are built by static/app.js once it knows
    which rows are still shown, so hiding a catalogue can shorten the reel
    without the markup lying about how many films there are.
    """
    slides = "".join(billboard_slide(item, index, row_id)
                     for index, (row_id, item) in enumerate(picks))
    # A carousel that moves by itself needs a way to stop it, which is both
    # what WCAG asks for and what anyone reading a synopsis wants.
    return ('<div class="bb-carousel" data-bb-carousel>%s'
            '<div class="bb-dots" data-bb-dots></div>'
            '<button class="bb-pause" type="button" data-bb-pause'
            ' aria-pressed="false" aria-label="Pause the carousel">'
            '<span data-bb-icon="pause">%s</span>'
            '<span data-bb-icon="play" hidden>%s</span></button>'
            '<div class="bb-progress" data-bb-progress aria-hidden="true">'
            '<i></i></div></div>' % (slides, ICON_PAUSE, ICON_PLAY))


def billboard_with_fallback(picks):
    """The carousel, plus the banner it becomes when every row is hidden."""
    if not picks:
        return billboard_fallback()
    return ('%s<div class="bb-fallback" data-bb-fallback hidden>%s</div>'
            % (billboard_carousel(picks), billboard_fallback()))

def home_page():
    # A first visit should look like a catalogue, not an empty shelf: the hero
    # and every row come from the addon before anybody has saved anything.
    try:
        rails_data = catalog.rows()
    except Exception:
        rails_data = []
    # more candidates than the reel needs: rows hidden in the browser are
    # dropped there, and ten films should still be left to show
    picks = catalog.picks(rails_data, 30) if rails_data else []
    hero = billboard_with_fallback(picks)

    rails = [shelf(name, "catalog-%s" % key,
                   "".join(library_card(one) for one in items))
             for key, name, items in rails_data]

    # What somebody saved and what they are part-way through comes first: the
    # catalogue is the shop window, these two are the shelf at home.
    return ("Home",
            '<div class="bb-host" data-billboard>%s</div>'
            '<div class="rows" data-rows>%s%s%s</div>'
            % (hero,
               shelf("Continue watching", "continue",
                     empty_text="Nothing part-watched yet. Start a film and "
                                "it shows up here.",
                     head_extra=continue_head_actions()),
               shelf("My list", "watchlist",
                     empty_text="Nothing saved yet. Use the + on any poster."),
               "".join(rails)),
            "english")


def search_hero(title_html, sub=""):
    return ('<section class="search-hero">%s%s%s</section>'
            % (title_html, ('<p class="lede">%s</p>' % esc(sub)) if sub else "",
               library_field()))


def search_page(query, items=(), movies=(), series=(), failed=False):
    """Cinemeta's index across the whole library, not one service at a time."""
    if query:
        count = "%d result%s" % (len(items), "" if len(items) == 1 else "s")
        body = [search_hero('<p class="eyebrow">Library &middot; %s</p>'
                            '<h1 class="display search-query">%s</h1>'
                            % (esc(count), esc(query)))]
        if items:
            body.append('<section class="results"><div class="grid">%s</div>'
                        '</section>' % "".join(library_card(i) for i in items))
        elif failed:
            body.append('<p class="empty bad">Cinemeta could not be reached '
                        'just now. Try again in a moment.</p>')
        else:
            body.append('<p class="empty">Nothing in the library matches '
                        '&ldquo;%s&rdquo;.</p>' % esc(query))
        return ("Search", "".join(body), "english")

    body = [search_hero(
        '<p class="eyebrow">Search</p>'
        '<h1 class="display">Find something to watch</h1>',
        "Every service on one shelf. A poster opens the film; playback runs "
        "in the player you pick.")]
    if movies:
        body.append('<section class="results"><div class="shelf-head">'
                    '<h2>Popular movies</h2></div><div class="grid">%s</div>'
                    '</section>' % "".join(library_card(i) for i in movies))
    if series:
        body.append('<section class="results"><div class="shelf-head">'
                    '<h2>Popular shows</h2></div><div class="grid">%s</div>'
                    '</section>' % "".join(library_card(i) for i in series))
    if not movies and not series:
        body.append('<p class="empty bad">Nothing could be loaded just now. '
                    'Search above, or reload in a moment.</p>')
    return ("Search", "".join(body), "english")


PERSONAL_ROWS = [("continue", "Continue watching"), ("watchlist", "My list")]


def home_rows():
    """Every row the home page can show, in its shipped order."""
    return PERSONAL_ROWS + [("catalog-%s-%s" % (kind, cid), name)
                            for kind, cid, name in catalog.ROWS]


def rows_panel():
    """Pick the rows and their order; the home page applies it on load."""
    items = "".join(
        '<li class="row-item" data-row-id="%s" data-row-title="%s">'
        '<label class="row-toggle"><input type="checkbox" checked>'
        '<span>%s</span></label>'
        '<span class="row-move">'
        '<button class="btn ghost tiny" type="button" data-move="-1"'
        ' aria-label="Move %s up">&uarr;</button>'
        '<button class="btn ghost tiny" type="button" data-move="1"'
        ' aria-label="Move %s down">&darr;</button></span></li>'
        % (esc(key), esc(name), esc(name), esc(name), esc(name))
        for key, name in home_rows())
    return (
        '<section class="panel rows-panel" data-rows-panel>'
        '<h2>Home page rows</h2>'
        '<p class="panel-note">Choose which rows the home page shows and in '
        'which order. Kept in this browser, next to your list.</p>'
        '<ol class="row-list" data-row-list>%s</ol>'
        '<button class="btn ghost tiny" type="button" data-rows-reset>'
        'Reset to default</button></section>' % items)


THEMES = [
    ("saffron", "Saffron", "#f2a33c"),
    ("ember", "Ember", "#e56b3a"),
    ("crimson", "Crimson", "#e0433f"),
    ("rose", "Rose", "#e86a92"),
    ("orchid", "Orchid", "#d267d8"),
    ("violet", "Violet", "#a78bfa"),
    ("indigo", "Indigo", "#7f8cf6"),
    ("azure", "Azure", "#4aa8f0"),
    ("teal", "Teal", "#3fbcae"),
    ("emerald", "Emerald", "#54c288"),
    ("lime", "Lime", "#a3c94f"),
    ("gold", "Gold", "#d9b544"),
    ("sand", "Sand", "#d3bb9c"),
    ("ice", "Ice", "#a8bed6"),
    ("slate", "Slate", "#96a4b4"),
]


def theme_panel():
    """Fifteen accents; the choice is applied in the browser and kept there."""
    swatches = "".join(
        '<button class="swatch" type="button" data-theme-option="%s"'
        ' style="--swatch:%s" aria-label="%s" title="%s"'
        ' aria-pressed="false"><span></span></button>'
        % (key, hexv, name, name)
        for key, name, hexv in THEMES)
    return (
        '<section class="panel theme-panel" data-theme-panel>'
        '<h2>Colour</h2>'
        '<p class="panel-note">The accent the whole site uses. Kept in this '
        'browser.</p>'
        '<div class="swatches" data-theme-list>%s</div></section>' % swatches)


def dwell_panel():
    """How long the hero holds each film; the browser applies and keeps it."""
    return (
        '<section class="panel dwell-panel" data-dwell-panel>'
        '<h2>Carousel speed</h2>'
        '<p class="panel-note">How long the home page hero holds each film '
        "before moving on, in whole seconds — ten by default. The bar along "
        "the bottom of the carousel counts it down.</p>"
        '<div class="dwell-field">'
        '<label for="dwell-seconds">Seconds per film</label>'
        '<input id="dwell-seconds" type="number" inputmode="numeric" '
        'min="1" max="600" step="1" value="10" data-dwell-input>'
        '<button class="btn ghost tiny" type="button" data-dwell-reset>'
        "Reset to 10</button></div></section>"
    )


def source_panel():
    """Where the code lives: the footer link, now a settings row."""
    return (
        '<section class="panel"><h2>Source</h2>'
        '<p class="panel-note">The code behind RogFlix is open on GitHub.'
        "</p>"
        '<a class="btn ghost" href="https://github.com/RegorTheDodger/RogFlix" target="_blank"'
        ' rel="noopener noreferrer">%sView source on GitHub</a></section>'
        % (ICON_GITHUB,)
    )


def settings_page(top_lang="english"):
    return ("Settings",
            '<section class="page-head">'
            '<p class="eyebrow">Preferences</p>'
            '<h1 class="h1">Settings</h1></section>'
            + theme_panel() + dwell_panel() +
            '<section class="panel auth-panel" data-auth-panel><h2>Sync between devices</h2>'
            '<p class="panel-note">Create an account or log in to sync your '
            "list, watch time and resume positions between your devices.</p>"
            '<p class="auth-status" data-auth-status role="status"></p>'
            '<div data-auth-guest>'
            '<form class="auth-form" data-auth-form="login" action="/auth/login" method="post">'
            '<input type="text" name="username" placeholder="Username" '
            'autocomplete="username" required>'
            '<input type="password" name="password" placeholder="Password" '
            'autocomplete="current-password" required>'
            '<button class="btn" type="submit">Log in</button></form>'
            '<form class="auth-form" data-auth-form="register" action="/auth/register" method="post">'
            '<input type="text" name="username" placeholder="New username" '
            'autocomplete="username" required>'
            '<input type="password" name="password" placeholder="New password (8+ characters)" '
            'autocomplete="new-password" required>'
            '<button class="btn ghost" type="submit">Create account</button></form>'
            '</div><div data-auth-user hidden>'
            '<p class="auth-welcome">Signed in as <b data-auth-name></b></p>'
            '<button class="btn ghost" type="button" data-auth-logout>Log out</button>'
            '</div>'
            '<form action="/auth/logout" method="post" hidden>'
            '<button class="btn ghost" type="submit">Log out</button></form>'
            '<p class="panel-note">Your list stays local until you log in; '
            "the browser syncs it after authentication.</p></section>"
            + rows_panel() +
            '<section class="panel"><h2>Stored data</h2>'
            '<p class="panel-note">Erase this browser\'s local list, watch time '
            "and resume positions.</p>"
            '<button class="btn ghost" type="button" data-action="clear-all">'
            "Erase everything</button></section>"
            + source_panel(),
            "english")
