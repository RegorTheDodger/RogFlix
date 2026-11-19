<p align="center"><img src="static/logo.webp" alt="RogFlix — every service, one shelf" width="200"></p>

<h1 align="center">RogFlix</h1>

<p align="center">
  <a href="https://rogflix.vercel.app"><img alt="Live site" src="https://img.shields.io/badge/live-rogflix.vercel.app-e04a2f?style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/flask-3.1-000000?style=flat-square&logo=flask&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/sync-postgresql-4169E1?style=flat-square&logo=postgresql&logoColor=white">
</p>

RogFlix puts everything the big streaming services are carrying on one shelf.
It reads the Streaming Catalogs addon — 35 services, films and series — paints a
home page of service-by-service rows, and plays any title through one of four
players — CineSrc, VidLink, VidSrc.sh and VidSrc.mov — picked under the frame. A
fifth, einthusan, is kept in the code but switched off for now (see
[Einthusan](#einthusan)). Search, My List, continue watching and an account that
merges those shelves between devices are all included.

The app is Flask with server-rendered HTML, a small vanilla-JavaScript layer for
the rails, the player bridge and the local-first list, and Postgres (or SQLite
locally) for accounts. No build step, no client-side framework.

> ### Start with the hosted site
>
> **<https://rogflix.vercel.app>** is the project, ready to use — no install,
> no database, no environment variables. The install steps below are for
> running it locally when you want to change the code.

## Table of contents

- [What it does](#what-it-does)
- [How the site works](#how-the-site-works)
- [How sync works](#how-sync-works)
- [Project structure](#project-structure)
- [Every file explained](#every-file-explained)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Roadmap and known issues](#roadmap-and-known-issues)
- [Contributing](#contributing)
- [Authors](#authors)
- [License](#license)

## What it does

- **One library, many services.** Netflix, Prime Video, JioHotstar, Disney+,
  HBO Max, Apple TV+, Zee5, Peacock and the rest, as separate rows instead of one
  undifferentiated grid.
- **A real title page.** Poster, backdrop, synopsis, cast, crew, runtime, rating,
  awards, trailer and the full episode list — none of which the catalogue addon
  itself provides.
- **Four sources, one picker.** CineSrc, VidLink, VidSrc.sh and VidSrc.mov
  under every title page, so a service missing the film is
  one click from the next.
- **Playback that resumes.** Films and single episodes open in CineSrc,
  VidLink or VidSrc.sh at the second you left them.
- **My List and continue watching** that work signed out and keep working on a
  phone and a laptop once you sign in.

## How the site works

**The catalogue.** RogFlix reads the Streaming Catalogs addon, which lists what
35 services are carrying — films and series separately. The home page opens with
a carousel of ten films drawn from the rows still shown, each holding for ten
seconds with a countdown along its bottom edge (the hold is adjustable on
`/settings`), then one row per service, painted
straight from the catalogue, so a first visit already looks like a library
rather than an empty shelf.

**Metadata.** The addon answers catalogues only: it has no synopsis or episode
list. Those come from Cinemeta, keyed by the IMDb id every catalogue entry
carries, which is also where the TMDB id for playback comes from. A card opens
its own page without a lookup; the poster, backdrop, cast, runtime, rating,
trailer and episode list all arrive together.

**Watching.** A title page carries a player and a picker under it: CineSrc,
VidLink, VidSrc.sh and VidSrc.mov, in that order. CineSrc and
VidLink key on the TMDB id — a film at `/movie/<tmdb>`, an episode at
`/tv/<tmdb>/<season>/<episode>` — while the VidSrc pair take a TMDB or an IMDb
id, so a title Cinemeta knows without a `moviedb_id` still plays. Both VidSrc
mirrors put `/embed/` in the path. The choice is
kept in the browser and comes back on the next visit. The frame is covered by
the poster until you press play, and a series opens on its first real season,
since season 0 is the specials list and has no episode to play. CineSrc
(`cinesrc:timeupdate`), VidLink and VidSrc.sh (`PLAYER_EVENT`) report position
as it goes, so the resume point and the watch time keep moving while any of them
is the source in use, and a series on VidLink shows the player's own
next-episode button near the end of an episode. VidSrc.mov reports nothing, so a
film watched through it does not move continue watching.

**Einthusan.** Switched off for now: `OFFER_EINTHUSAN` in `lib/players.py` is
`False`, so no title page offers the button, and the client, the source logic
and the `/einthusan` routes stay in the tree so it can come back by flipping
that one flag. While it was on, Indian films got a fifth source: einthusan,
which has no embed
URL of its own and signs an mp4 per viewing instead — it indexes eight Indian
languages and carries nothing from outside India. So that button points
at a page here: it searches einthusan's eight language indexes for the film by
title and year, plays what it finds in the frame with the site's own resume,
and names the language playing under the player. A film einthusan carries in
more than one language is a different dub in each, so every index holding it
becomes a button across the top of the frame: pressing one swaps the stream at
the same second, and the language playing is marked as the original or a dub.
The default is always the film's original language. Cinemeta records a film's
country but not its language, so the language field of the film's Wikipedia
infobox is read once per film and kept for a week; when an article says
nothing, the closest title match plays. The scan runs when the frame asks for
the film, and its answer is kept in memory for a few hours, so switching
languages or reopening the same film does not read the indexes again.
Films from anywhere else never see the source, and neither does a series. A
film einthusan does not have says so in the frame rather than sitting blank.

**Search.** The search box queries Cinemeta across the whole library and keeps
only titles that resemble what was typed — punctuation and spacing ignored, so
"spiderman 3" finds *Spider-Man 3*. With no query the page shows popular films
and shows instead of an empty form.

**Home rows.** Continue watching and My list open the home page; the service rows
follow. Settings → Home page rows chooses which rows appear and in what order,
kept in the browser beside your list.

**My List.** The + on any poster saves the title locally, instantly, with no
account needed. A show is saved as the show, not as whichever episode was open,
and the list page keeps films and shows in their own grids under a count.
Removing one writes a timestamped tombstone so a stale device cannot bring it
back.

**Continue watching.** The player writes a resume position and the shelf shows
what is part-watched, most recent first. A title earns a card after ten seconds
of real playback; a jump longer than six seconds counts as a seek, not watching;
the position is saved at most every four seconds; and in the player's last
minute and a half the film counts as finished and leaves the shelf (a share of
the reported duration would misfire on streams that claim a shorter runtime). For a series the resume point is per episode,
while My List holds the show.

## How sync works

Everything works signed out. The browser owns the list, the resume points and the
watch time, which is why the site is instant and survives a dropped connection.

An account adds a second copy. When you sign in, the device posts its whole state
and the server returns the **merge** of the two — never a replacement. Merging is
what makes a phone and a laptop safe on one account: a film added on one is not
erased by an older copy from the other.

- **My List** — newest add per title wins; a removal is a tombstone that outvotes
  older adds and expires after 180 days.
- **Continue watching** — newest position wins; once a title is marked started it
  stays started, whichever device said so first.
- **Watch time** — the newer record supplies the metadata, but play time keeps
  the larger tally. "Finished" belongs to the later record, so a film watched
  again (a newer resume point) stops counting as finished.
- **Titles and covers** — merged field by field, so a known title or cover is
  never replaced by a blank.
- **Finishing or clearing** a title drops the resume point rather than sending a
  device backwards.
- **Theme, home rows and carousel speed** — one preference stamp, newest change
  wins, because an accent is a single choice, an order is a whole arrangement
  and a speed is one number, none of them something to merge item by item.

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a per-user salt, and a
session is a random token whose hash — not the token — is kept. Attempts are
throttled per address. Total synced state is capped, so a broken client cannot
post a gigabyte of junk.

## Project structure

```text
rogflix/
├── app.py                  local development server
├── api/
│   └── index.py            Vercel serverless entry point
├── lib/
│   ├── __init__.py         marks lib/ as a package
│   ├── webapp.py           Flask app: routes, auth, sync endpoints
│   ├── views.py            all HTML rendering
│   ├── stremio.py          Cinemeta client + search + metadata cache
│   ├── catalog.py          Streaming Catalogs client (home rows)
│   ├── players.py          the five sources and their URLs
│   ├── einthusan.py        einthusan client: search, indexes, signed media
│   ├── einthusan_source.py finds an Indian film for the fifth source
│   ├── language.py        a film's original language, from Wikipedia
│   ├── accounts.py         users, sessions, signup modes
│   ├── sync.py             merge rules for the personal state
│   └── db.py               Postgres/SQLite connection + schema
├── static/
│   ├── app.js              list, player bridge, rails, row settings
│   ├── motion.js           scroll reveal and small page animations
│   ├── style.css           every style in the site
│   ├── manifest.json       PWA metadata
│   ├── logo.webp           full logo (README and social previews)
│   ├── mark.png            the nav mark / emblem crop
│   ├── icon-192.png        PWA icon
│   ├── icon-512.png        PWA icon, large
│   ├── logo-180.png        apple-touch-icon
│   ├── favicon-32.png      browser tab icon
│   └── og.png             1200×630 social card
├── tests/
│   └── test_logic.py       gate, matching, language and the merge rules
├── requirements.txt        Flask and pg8000, pinned
├── vercel.json             Vercel function settings
├── .vercelignore           files Vercel must not upload
├── .gitignore              files git must not track
└── README.md               this file
```

## Every file explained

**`app.py`** — the local dev server. Builds the Flask app and runs it on
`127.0.0.1` at the port you pass (`python app.py 8091`), bound to `0.0.0.0` so a
phone on the same Wi-Fi can reach it. Vercel never runs this file.

**`api/index.py`** — the Vercel entry point. It only puts the project root on
`sys.path` and exposes `app = create_app()`, because Vercel expects a WSGI
callable at that path. Keeping it separate from `app.py` is what lets the same
application run in both places.

**`lib/__init__.py`** — empty; it marks `lib` as a package so both entry points
can import from it.

**`lib/webapp.py`** — the Flask application and its routes: `/`, `/search`,
`/title/<kind>/<id>`, `/watchlist`, `/settings`, the `/auth/*` login and signup
endpoints, `/api/sync` (GET and POST), `/api/sync/clear`, the `/library`
redirects kept for old bookmarks, and `/healthz`. It reads request arguments,
decides the season and episode being asked for, calls the accounts and sync
modules, and hands a body to `views`.

**`lib/views.py`** — every piece of HTML. It has the page shell (head, nav), the
home page with its rows, search, the title page with the player and
the episode list, My List, settings, and all the shared pieces: `shelf()` for a
row, `library_card()` for a poster, `esc()` for escaping, plus the hero fallback.
Nothing here talks to the network; it renders what it is given.

**`lib/stremio.py`** — the Cinemeta client. Fetching with a timeout and two
attempts, an in-process TTL cache with a stale copy for a provider having a bad
minute, a small disk cache for searches, `catalog()`/`search()`/`meta()`,
episode parsing, and the ranking that decides whether a search result actually
resembles the query. It also carries `moviedb_id` through as `tmdb`, which is
what the player needs.

**`lib/catalog.py`** — the Streaming Catalogs client. Defines the eight rows the
home page asks for (service + film or series), fetches them in parallel with a
15-minute cache, normalises each entry to the card shape, and offers the films
the hero carousel draws from — one per film row, then a second from each, so no
single service owns the top of the page. Each candidate carries its row id, and
the browser keeps ten from the rows it still shows; hiding every film row leaves
the search banner in place of the hero. Row ids are service-based (`catalog-movie-nfx`)
rather than positional, so settings can hide or reorder them safely.

**`lib/players.py`** — the sources. Turns a title's TMDB and IMDb ids and an
optional season/episode into one URL per service — CineSrc, VidLink, VidSrc.sh,
VidSrc.mov, einthusan — in the order the page offers them,
adding the accent colour where a player accepts one, the next-episode button on
a VidLink series, and the query parameter each one takes for a start second.
Einthusan is gated twice: it is offered only for films Cinemeta lists as Indian,
and only while `OFFER_EINTHUSAN` is on.

**`lib/einthusan.py`** — the einthusan client, taken from the EinthuFlix app.
It reads the eight language indexes, searches them (with a shorter-prefix
fallback for a typo), parses a watch page, and lifts the signed mp4 out of it,
re-caching a signature shortly before it expires. Nothing else in the site
knows einthusan's HTML.

**`lib/einthusan_source.py`** — the fifth source's own logic, and the only file
that decides whether it is offered: the India-only country check, the search
across every language index, the title-and-year match that keeps the best entry
per language (so the frame can offer them all and start on the original), and
the small memory of hits and misses that keeps a second visit instant.

**`lib/language.py`** — the language a film was made in. Cinemeta has a film's
country but not its language, and einthusan's index entries do not say whether
they are a dub, so this finds the film's Wikipedia article and reads the
`language` field of its infobox (falling back to the first sentence). The
year has to be on the page too, so a same-named film cannot lend its language.
That is asked once per film, kept for a week, and needs no key. A miss costs
nothing: the frame then starts on whichever index matched the title best, and
the language buttons are there either way.

**`lib/accounts.py`** — users and sessions. Password hashing (PBKDF2-HMAC-SHA256,
per-user salt), session token creation and lookup (only the SHA-256 of the token
is stored), the signup modes (`first`, `open`, `closed`), signup and login
throttling, and the state read/write used by sync.

**`lib/sync.py`** — the merge rules. Given the state two devices posted, it
returns one: newest list add wins, tombstones beat older adds, newest resume
position wins, started stays started, watch time keeps the larger tally, and
metadata is merged field by field. It also caps the payload size.

**`lib/db.py`** — storage. Picks Postgres when a URL is in the environment and
SQLite at `.data/rogflix.db` otherwise, opens connections, runs the small query
wrapper used everywhere, and creates the tables on first use. This is the only
file that knows a database dialect.

**`static/app.js`** — the browser side: localStorage for My List, resume points
and watch time, painting those shelves, the source picker under the player and
the VidLink `PLAYER_EVENT` bridge (play, pause, seeked, timeupdate, ended), each
player's accent parameter retinted to the theme picked on settings, the poster
gate, rail scrolling,
search-box behaviour, the account/sync calls, the home-row order stored by
settings, and the hero carousel: which rows its films come from, the hold
between films and the countdown under them.

**`static/motion.js`** — presentation only: the reveal-on-scroll and any small
transitions, kept out of `app.js` so the data layer stays readable. Every page
works if it fails to load.

**`static/style.css`** — the whole design system in one file: tokens (colour,
type, spacing, radii), layout, nav, hero, shelves and cards, title page, player
gate, settings panels, the home-row list, responsive rules for narrow screens,
and the reduced-motion handling.

**`static/manifest.json`** — the web app manifest: name, colours, and the 192 and
512 icons, so the site can be installed to a home screen.

**`static/logo.webp`** — the full logo with the wordmark, used by this README and
as the brand image in previews.

**`static/mark.png`** — the square emblem crop used as the 32 px nav badge. The
full logo's text is unreadable at that size, so only the artwork is used there.

**`static/icon-192.png`, `static/icon-512.png`** — PWA icons, referenced by the
manifest.

**`static/logo-180.png`** — the apple-touch-icon for iOS home screens.

**`static/favicon-32.png`** — the tab icon.

**`static/og.png`** — the 1200×630 social card (`og:image`), the logo on the
brand red.

**`requirements.txt`** — the two runtime dependencies, pinned: Flask 3.1.0 and
pg8000 1.31.6 (a pure-Python Postgres driver, so no compiler is needed).

**`vercel.json`** — deployment settings: raises the Python function's
`maxDuration` to 30 seconds. Routing is left to Vercel's defaults, which already
send every path to `api/index.py` and serve `static/` directly.

**`.vercelignore`** — keeps `.env`, `.venv`, `__pycache__`, `.data` and `.DS_Store`
out of a deployment.

**`.gitignore`** — keeps `.vercel`, `.data/`, caches, `.env` files and
`.DS_Store` out of the repository.

**`README.md`** — this document.

## Installation

> Reminder: for normal use, just open **<https://rogflix.vercel.app>**. Install
> locally only to run or change the code.

**Requirements**

- Python 3.10 or newer
- pip and a terminal
- Optional: PostgreSQL 13+ for account sync across machines. Without it, the app
  writes to a local SQLite file, which covers everything except signing in from
  more than one device.

**Steps**

```bash
git clone https://github.com/RegorTheDodger/RogFlix.git
cd RogFlix

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

That is the whole install: the catalogue, metadata and player are remote
services, and there is no build step.

## Usage

```bash
python app.py 8091
```

```text
RogFlix
  http://127.0.0.1:8091
  http://<mac-ip>:8091
```

Open <http://127.0.0.1:8091>. The first visit needs no account: rows, search and
playback all work signed out, and My List starts in the browser.

**Create the first account.** Go to `/settings` and register. With the default
`first` signup mode the first account is the owner and later registrations are
refused; `ROGFLIX_ALLOW_SIGNUP=open` opens it up (see
[Configuration](#configuration)).

**Useful routes**

```text
/search?q=dune                     search the whole library
/title/movie/tt15239678            a film's page and player
/title/series/tt7587890?s=1&e=2    one episode
/einthusan/tt1745960?t=300         the fifth source's frame, at 5:00
/einthusan/tt1745960?lang=tamil    the same, in Tamil
/api/status                        whether each player answers, cached 5 min
/api/up-next/movie/tt1745960       what to watch after it, by genre
/watchlist                         My List
/settings                          account, home rows, stored data
/healthz                           JSON: database dialect and app state
```

- Press the + on any poster to add it to My List.
- Press Play on a title page to reveal the player; it opens at your saved second
  in CineSrc, VidLink or VidSrc.sh. If a source will not load, pick
  another under the frame, and the page says so if nothing loads at all.
- The hero carousel has a pause button (an icon, not a word), and it starts
  paused when the system asks for reduced motion.
- A title you were part-way through says where it will pick up: "Resumed at
  2h 58m."
- When a player reports the end, an Up next row appears under the frame: the
  next episode, and a dozen titles from the same genres.
- In the einthusan frame, the language buttons switch the copy at the same
  second; the choice is remembered for that film, and the address keeps it, so a
  reload or a shared link plays the same language.
- Watch ten seconds and the title appears under Continue watching.
- In `/settings`, under **Home page rows**, untick a row or move it with the
  arrows; the home page follows on the next load.
- **Colour** in `/settings` picks one of fifteen palettes for the whole site —
  the accent, and the room it sits in (inks, paper, hairlines, scrims) are all
  mixed from it — kept in the browser.
- The **Source** panel at the bottom of `/settings` links to the GitHub
  repository.
- **Carousel speed** in `/settings` sets how long each film in the hero holds —
  ten seconds unless you change it; the countdown bar follows the number.
- Sign in and the next visit merges this browser's list with the account's.

## Configuration

Every setting is an environment variable; all are optional for local use.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROGFLIX_DATABASE_URL` | local SQLite `.data/rogflix.db` | Postgres URL for accounts and sync. `DATABASE_URL` and `POSTGRES_URL` are accepted too |
| `ROGFLIX_DB_PATH` | `.data/rogflix.db` | Where the SQLite file lives when no Postgres URL is set |
| `ROGFLIX_ALLOW_SIGNUP` | `first` | `first` (owner only), `open` (anyone), `closed` (no registrations) |
| `CINEMETA_URL` | `https://v3-cinemeta.strem.io` | Metadata provider |
| `CATALOG_ADDON` | the public Streaming Catalogs addon | Catalogue provider |

Example with a local Postgres:

```bash
export ROGFLIX_DATABASE_URL="postgresql://user:pass@localhost:5432/rogflix"
python app.py 8091
```

The tables are created on first use; there is no migration step.

## Roadmap and known issues

**Known issues**

- Every source is third-party. When one is missing a title, or its own
  sources fail, switch source under the frame — this app cannot fix their
  bundles, and only CineSrc, VidLink and VidSrc.sh report progress back to it.
- Einthusan has one entry per language. A film it carries in several starts on
  the original when Wikipedia names it, and the other indexes are buttons across
  the frame; a dub with no button is one einthusan does not carry. Its signed
  links expire after six hours, which the frame recovers from on its own by
  asking for a new link and resuming at the same second.
- A title Cinemeta has no TMDB id for has no player, and the page says so
  instead of showing an empty frame.
- Season 0 (specials) is listed but not playable.
- Home row layout is per browser; it is not part of the synced account state.
- Rows and metadata depend on two public addons: if either is down, a row or a
  page can come back empty.


## Contributing

Bug reports and feature requests are welcome in
[Issues](https://github.com/RegorTheDodger/RogFlix/issues). For a pull request,
keep it small and in the shape of the existing code: server-rendered HTML in
`lib/views.py`, behaviour in `static/app.js`, no new framework and no build step.
Please run the app locally and say which page you changed.

## Authors

Built and maintained by [RegorTheDodger](https://github.com/RegorTheDodger).

- Bug reports: [GitHub Issues](https://github.com/RegorTheDodger/RogFlix/issues)
- Source: [github.com/RegorTheDodger/RogFlix](https://github.com/RegorTheDodger/RogFlix)

## License

No open-source license has been applied to this repository yet: all rights are
reserved by the author, and the code may not be redistributed or reused without
permission. If you want others to be able to use it, add a `LICENSE` file (MIT
and Apache-2.0 are the usual choices) and replace this section with its name and
a link to that file.
