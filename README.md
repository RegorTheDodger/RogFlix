<p align="center"><img src="static/logo.webp" alt="RogFlix" width="220"></p>

# RogFlix

Films and shows from every big streaming service, on one shelf: search, a
player, My List, continue watching and accounts that keep those shelves in step
across devices.

## How the site works

**The catalogue.** RogFlix reads the Streaming Catalogs addon, which lists what
35 services are carrying — Netflix, Prime Video, JioHotstar, Disney+, HBO Max,
Apple TV+, Zee5, Peacock and the rest — as films and as series. The home page
opens with a featured film and then one row per service, each row painted
straight from the catalogue, so a first visit already looks like a library
rather than an empty shelf.

**Metadata.** The addon answers catalogues only: it has no synopsis or episode
list. Those come from Cinemeta, keyed by the IMDb id every catalogue entry
carries. That is why a card can open its own page without a lookup, and why a
film's poster, backdrop, cast, runtime, rating, trailer and episode list all
arrive together.

**Watching.** A title page carries the CineSrc embed, which is keyed by TMDB
id — a film at `/embed/movie/<tmdb>`, an episode at
`/embed/tv/<tmdb>?s=<season>&e=<episode>`. Cinemeta returns that id with every
title, so the page never has to guess one. The frame is covered by the poster
until you press play. A series opens on its first real season; season 0 is the
specials list, which has no episode to play. When a series rolls into its next
episode inside the player, the page follows it: the address bar, the resume
point and the watch time all move to the episode now playing.

**Search.** The search box queries Cinemeta across the whole library, and keeps
only titles that resemble what was typed — punctuation and spacing ignored, so
"spiderman 3" finds *Spider-Man 3*. With no query the page shows popular films
and shows instead of an empty form.

**Home rows.** The home page opens with Continue watching and My list, then
the service rows. Settings → Home page rows picks which of them appear and in
what order, and the choice is kept in this browser.

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

Everything works signed out. The browser owns the list, the resume points and
the watch time, which is why the site is instant and survives a dropped
connection.

An account adds a second copy. When you sign in, the device posts its whole
state and the server returns the **merge** of the two — never a replacement.
Merging is what makes a phone and a laptop safe on one account: a film added on
one is not erased by an older copy from the other.

- **My List** — newest add per title wins; a removal is a tombstone that
  outvotes older adds and expires after 180 days.
- **Continue watching** — newest position wins; once a title is marked started
  it stays started, whichever device said so first.
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

## RogFlix vs EinthuFlix

The two sites are deliberately separate products; neither links to the other,
and they share no catalogue and no account database.

| | **RogFlix** | **EinthuFlix** |
| --- | --- | --- |
| Library | Everything the big streaming services carry, across 35 services | South Asian cinema only — eight Indian languages |
| Where titles come from | Streaming Catalogs (Stremio) rows, metadata from Cinemeta | einthusan's language indexes |
| Playback | CineSrc embed by TMDB id | einthusan's signed mp4 in a native player |
| Browsing | One row per service, plus popular films and shows on search | Language tabs, Most Watched, Staff Picks, Recently Added |
| Search | Full-library search by title | Prefix search inside one language |
| Best for | Finding a specific film or show from Netflix, Prime Video, JioHotstar, Disney+, HBO Max, Zee5 and the rest | Finding a Tamil, Telugu, Malayalam, Kannada, Hindi, Bengali, Marathi or Punjabi film |

RogFlix is the broader shelf; EinthuFlix is the deeper one. Both run the same
player behaviour, the same My List and continue watching, and the same
merge-on-sync accounts described above.
