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
home page of service-by-service rows, and plays any title through the CineSrc
player. Search, My List, continue watching and an account that merges those
shelves between devices are all included.

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
- **Playback that resumes.** Films and single episodes open in CineSrc at the
  second you left them.
- **My List and continue watching** that work signed out and keep working on a
  phone and a laptop once you sign in.

## How the site works

**The catalogue.** RogFlix reads the Streaming Catalogs addon, which lists what
35 services are carrying — films and series separately. The home page opens with
a featured film and then one row per service, painted straight from the
catalogue, so a first visit already looks like a library rather than an empty
shelf.

**Metadata.** The addon answers catalogues only: it has no synopsis or episode
list. Those come from Cinemeta, keyed by the IMDb id every catalogue entry
carries, which is also where the TMDB id for playback comes from. A card opens
its own page without a lookup; the poster, backdrop, cast, runtime, rating,
trailer and episode list all arrive together.

**Watching.** A title page carries the CineSrc embed, which is keyed by TMDB id —
a film at `/embed/movie/<tmdb>`, an episode at
`/embed/tv/<tmdb>?s=<season>&e=<episode>`. The frame is covered by the poster
until you press play. A series opens on its first real season; season 0 is the
specials list, which has no episode to play. When a series rolls into its next
episode inside the player, the page follows it: the address bar, the resume point
and the watch time all move to the episode now playing.

**Search.** The search box queries Cinemeta across the whole library and keeps
only titles that resemble what was typed — punctuation and spacing ignored, so
"spiderman 3" finds *Spider-Man 3*. With no query the page shows popular films
and shows instead of an empty form.

**Home rows.** Continue watching and My list open the home page; the service rows
follow. Settings → Home page rows chooses which rows appear and in what order,
kept in the browser beside your list.

**My List.** The + on any poster saves the title locally, instantly, with no
account needed. A show is saved as the show, not as whichever episode was open.
Removing one writes a timestamped tombstone so a stale device cannot bring it
back.

**Continue watching.** The player writes a resume position and the shelf shows
what is part-watched, most recent first. A title earns a card after ten seconds
of real playback; a jump longer than six seconds counts as a seek, not watching;
the position is saved at most every four seconds; and at 95% the film counts as
finished and leaves the shelf. For a series the resume point is per episode,
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
  the larger tally and "finished" stays true once true.
- **Titles and covers** — merged field by field, so a known title or cover is
  never replaced by a blank.
- **Finishing or clearing** a title drops the resume point rather than sending a
  device backwards.

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
│   ├── cinesrc.py          CineSrc player URLs
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

**`lib/views.py`** — every piece of HTML. It has the page shell (head, nav,
footer), the home page with its rows, search, the title page with the player and
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
15-minute cache, normalises each entry to the card shape, and picks the featured
title for the hero. Row ids are service-based (`catalog-movie-nfx`) rather than
positional, so settings can hide or reorder them safely.

**`lib/cinesrc.py`** — the player. Turns a TMDB id and an optional season/episode
into a CineSrc embed URL, adding the default accent colour, the seek-button
length, and — when resuming — `t` and `continueprompt=false` so the frame opens
where the page says without a second prompt.

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
and watch time, painting those shelves, the CineSrc `postMessage` bridge (play,
pause, timeupdate, ended, error, next episode), the frame's `color` parameter
retinted to the theme picked on settings, the poster gate, rail scrolling,
search-box behaviour, the account/sync calls, and the home-row order stored by
settings.

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
/watchlist                         My List
/settings                          account, home rows, stored data
/healthz                           JSON: database dialect and app state
```

- Press the + on any poster to add it to My List.
- Press Play on a title page to reveal the CineSrc frame; it opens at your saved
  second.
- Watch ten seconds and the title appears under Continue watching.
- In `/settings`, under **Home page rows**, untick a row or move it with the
  arrows; the home page follows on the next load.
- **Colour** in `/settings` picks one of fifteen accents for the whole site,
  kept in the browser.
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

- CineSrc is a third-party player. When one of its sources fails it shows its own
  toast (for example `script load failed: response crypto unavailable`); pick
  another source in the player or reload — this app cannot fix their bundle.
- A title Cinemeta has no TMDB id for has no player, and the page says so
  instead of showing an empty frame.
- Season 0 (specials) is listed but not playable.
- Home row layout is per browser; it is not part of the synced account state.
- Rows and metadata depend on two public addons: if either is down, a row or a
  page can come back empty.

**Roadmap**

- Row layout synced with the account.
- Inline trailer playback instead of a YouTube tab.
- Keyboard shortcuts for the player and the rails.

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
