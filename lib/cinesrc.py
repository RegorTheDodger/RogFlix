"""
Playback through CineSrc.

CineSrc is the movie and television player this site streams from. It is keyed
by TMDB ids and documents two shapes (https://cinesrc.st/docs):

    https://cinesrc.st/embed/movie/{tmdb_id}
    https://cinesrc.st/embed/tv/{tmdb_id}?s={season}&e={episode}

Nothing is downloaded, converted or proxied here: the player is somebody
else's frame, which is what makes it behave the same on the Mac and on Vercel.

The knobs this app sets are all documented:

  * `t` opens the film at a second and `continueprompt=false` seeks straight
    there — this site prints its own "resumed at" note, so the player's
    Continue/Restart prompt would only be a second ask for the same thing;
  * `color` carries the site's saffron into the player;
  * `autonext` stays at its default, so a series rolls into the next episode
    inside the frame. static/app.js follows that move (cinesrc:nextepisode) by
    pointing the address bar, the saved position and the watch time at the
    episode now playing.

Playback events arrive over postMessage as `cinesrc:*`, which is how resume,
watch time and finished state stay in this app and follow an account between
devices.
"""

import re
import urllib.parse

BASE = "https://cinesrc.st"

# --saffron in style.css: what the frame gets when nothing else is picked.
# static/app.js replaces it with the accent chosen on /settings before the
# frame loads, so the player follows the theme rather than this default.
ACCENT = "#f2a33c"

# the player's own seek button; its documented default is fine
SEEK_BUTTON = 10


def _tmdb_id(value):
    """TMDB ids are numeric. Cinemeta hands them over as an int or a string."""
    return re.sub(r"\D", "", str(value if value is not None else ""))


def available():
    return True


def embed_url(kind, tmdb_id, season=0, episode=0, start=0):
    """The player URL for a film or one episode, or "" when unusable.

    Only TMDB ids: that is the key CineSrc documents, and it comes from
    Cinemeta's moviedb_id, so a title page has either a real player or no
    player at all — never a guess that fails silently.
    """
    tmdb = _tmdb_id(tmdb_id)
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

    params.append(("color", ACCENT))
    params.append(("seek", SEEK_BUTTON))
    if start and start > 0:
        params.append(("t", int(start)))
        params.append(("continueprompt", "false"))

    return "%s%s?%s" % (BASE, path, urllib.parse.urlencode(params))
