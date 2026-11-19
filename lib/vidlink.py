"""
Playback through VidLink.

VidLink is the movie and television player this site streams from. It is keyed
by TMDB ids and documents two shapes (https://vidlink.pro):

    https://vidlink.pro/movie/{tmdb_id}
    https://vidlink.pro/tv/{tmdb_id}/{season}/{episode}

Nothing is downloaded, converted or proxied here: the player is somebody
else's frame, which is what makes it behave the same on the Mac and on Vercel.

The knobs this app sets are all documented:

  * `primaryColor` carries the site's saffron into the player (a hex code
    without the "#"); static/app.js replaces it with the accent picked on
    /settings before the frame loads;
  * `startAt` opens the film at a second when a resume point exists;
  * `nextbutton` shows the player's own next-episode button on a series once
    an episode is nearly watched.

Playback events arrive over postMessage as `PLAYER_EVENT` messages (play,
pause, seeked, ended, timeupdate) with `currentTime` and `duration`, which is
how resume, watch time and finished state stay in this app and follow an
account between devices.
"""

import re
import urllib.parse

BASE = "https://vidlink.pro"

# --saffron in style.css, without the "#": what the frame gets when nothing
# else is picked. static/app.js replaces it with the accent chosen on /settings.
ACCENT = "f2a33c"


def _tmdb_id(value):
    """TMDB ids are numeric. Cinemeta hands them over as an int or a string."""
    return re.sub(r"\D", "", str(value if value is not None else ""))


def available():
    return True


def embed_url(kind, tmdb_id, season=0, episode=0, start=0):
    """The player URL for a film or one episode, or "" when unusable.

    Only TMDB ids: that is the key VidLink documents, and it comes from
    Cinemeta's moviedb_id, so a title page has either a real player or no
    player at all — never a guess that fails silently.
    """
    tmdb = _tmdb_id(tmdb_id)
    if not tmdb:
        return ""

    if kind == "series":
        if not season or not episode:
            return ""
        path = "/tv/%s/%d/%d" % (tmdb, int(season), int(episode))
    else:
        path = "/movie/%s" % tmdb

    params = [("primaryColor", ACCENT)]
    if kind == "series":
        params.append(("nextbutton", "true"))
    if start and start > 0:
        params.append(("startAt", int(start)))

    return "%s%s?%s" % (BASE, path, urllib.parse.urlencode(params))
