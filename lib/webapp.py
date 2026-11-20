"""
The Flask app, shared by the local dev server and the Vercel function.

Routes
  GET  /                 continue watching and my list
  GET  /search           ?q=&lang=
  GET  /watch/<id>       ?t=&c=&y=&l=   player
  GET  /watchlist
  GET  /settings         POST saves the default language
  GET  /convert          ?u=  and optionally &check=1
  GET  /title/<kind>/<id>  ?s=&e=  one film or one episode, and its player
"""

import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import quote, urlsplit

from flask import Flask, Response, jsonify, redirect, request

from . import accounts
from . import einthusan_source
from . import players
from . import stremio
from . import views

SESSION_COOKIE = "rogflix_session"


def _int_arg(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def create_app():
    # this module lives in lib/, so Flask would otherwise look for lib/static
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        static_folder=os.path.join(project_root, "static"),
        static_url_path="/static",
    )
    app.config["JSON_SORT_KEYS"] = False

    def render(name, body):
        return Response(views.page(name, body), mimetype="text/html; charset=utf-8")

    def current_user():
        return accounts.user_for_token(request.cookies.get(SESSION_COOKIE))

    def auth_response(payload, status=200):
        if not request.is_json:
            return redirect("/settings", code=303)
        return jsonify(payload), status

    def require_user():
        user = current_user()
        if not user:
            return None, (jsonify({"error": "Login required."}), 401)
        return user, None

    def secure_cookie():
        """True on the HTTPS deployment, false on localhost.

        Vercel terminates TLS and forwards the original scheme, so the request
        itself arrives as plain HTTP even when the visitor is on https.
        """
        if request.is_secure:
            return True
        return request.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def same_origin():
        """Whether a state-changing request came from a page on this site.

        SameSite=Lax already stops a cross-site form post from carrying the
        session; this is the second lock, and it also covers a browser that
        treats Lax differently from the spec.
        """
        origin = request.headers.get("Origin")
        if not origin:
            return True
        return urlsplit(origin).netloc == request.host

    # ---------------------------------------------------------------- home
    @app.route("/")
    def home():
        _name, body, _l = views.home_page()
        return render("Home", body)

    # -------------------------------------------------------------- search
    @app.route("/search")
    def search():
        query = (request.args.get("q") or "").strip()[:80]

        # No query shows what Cinemeta calls popular: the same index the rows
        # come from, so the page is never an empty form.
        if not query:
            movies, shows = [], []
            with ThreadPoolExecutor(max_workers=2) as pool:
                movie_job = pool.submit(stremio.popular, "movie")
                show_job = pool.submit(stremio.popular, "series")
                try:
                    movies = movie_job.result(timeout=9)[:24]
                except Exception:
                    movies = []
                try:
                    shows = show_job.result(timeout=9)[:24]
                except Exception:
                    shows = []
            _n, body, _l = views.search_page("", movies=movies, series=shows)
            return render("Search", body)

        results, failed = [], False
        try:
            results = stremio.search(query)
        except Exception:
            failed = True
        _n, body, _l = views.search_page(query, results, failed=failed)
        return render("Search", body)

    # -------------------------------------------------------------- player
    # ----------------------------------------------------------- watchlist
    @app.route("/watchlist")
    def watchlist():
        _n, body, _l = views.watchlist_page()
        return render("Watchlist", body)

    # ------------------------------------------------------------ settings
    @app.route("/settings")
    def settings():
        _n, body, _l = views.settings_page()
        return render("Settings", body)

    # --------------------------------------------------------------- account
    @app.route("/auth/me")
    def auth_me():
        user = current_user()
        return jsonify({"authenticated": bool(user), "user": user})

    @app.route("/auth/register", methods=["POST"])
    def auth_register():
        data = request.get_json(silent=True) or request.form
        try:
            user, error, status = accounts.register(
                data.get("username", ""), data.get("password", ""),
                request.remote_addr or "")
        except accounts.Unavailable:
            return auth_response({"error": "Account storage is unavailable."}, 503)
        if not user:
            return auth_response({"error": error}, status)
        token = accounts.create_session(user["username"])
        response = auth_response({"authenticated": True, "user": user}, 201)
        if request.is_json:
            response[0].set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                   httponly=True, samesite="Lax",
                                   secure=secure_cookie())
        else:
            response = redirect("/settings", code=303)
            response.set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                httponly=True, samesite="Lax",
                                secure=secure_cookie())
        return response

    @app.route("/auth/login", methods=["POST"])
    def auth_login():
        data = request.get_json(silent=True) or request.form
        try:
            user, error, status = accounts.login(
                data.get("username", ""), data.get("password", ""),
                request.remote_addr or "")
        except accounts.Unavailable:
            return auth_response({"error": "Account storage is unavailable."}, 503)
        if not user:
            return auth_response({"error": error}, status)
        token = accounts.create_session(user["username"])
        response = auth_response({"authenticated": True, "user": user})
        if request.is_json:
            response[0].set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                   httponly=True, samesite="Lax",
                                   secure=secure_cookie())
        else:
            response = redirect("/settings", code=303)
            response.set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                httponly=True, samesite="Lax",
                                secure=secure_cookie())
        return response

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
        if not same_origin():
            return jsonify({"error": "Cross-site request refused."}), 403
        token = request.cookies.get(SESSION_COOKIE)
        accounts.delete_session(token)
        response = auth_response({"authenticated": False})
        response[0].delete_cookie(SESSION_COOKIE) if request.is_json else response.delete_cookie(SESSION_COOKIE)
        return response

    @app.route("/api/sync", methods=["GET", "POST"])
    def sync_state():
        user, error = require_user()
        if error:
            return error
        if request.method == "GET":
            state, rev, updated = accounts.load_state(user["username"])
            return jsonify({"state": state, "rev": rev, "updated": updated})
        if not same_origin():
            return jsonify({"error": "Cross-site request refused."}), 403
        incoming = request.get_json(silent=True)
        if not isinstance(incoming, dict):
            return jsonify({"error": "A JSON state object is required."}), 400
        try:
            state, rev, updated = accounts.save_state(user["username"], incoming)
        except ValueError:
            return jsonify({"error": "Sync data is too large."}), 413
        except accounts.Unavailable:
            return jsonify({"error": "Account storage is unavailable."}), 503
        return jsonify({"state": state, "rev": rev, "updated": updated})

    @app.route("/api/sync/clear", methods=["POST"])
    def sync_clear():
        user, error = require_user()
        if error:
            return error
        if not same_origin():
            return jsonify({"error": "Cross-site request refused."}), 403
        state, rev, updated = accounts.clear_state(user["username"])
        return jsonify({"state": state, "rev": rev, "updated": updated})

    # ------------------------------------------------------------- convert
    # -------------------------------------------------------------- library
    # The library page is gone: English is a language on /search now, and the
    # old addresses keep working for anything already bookmarked.
    @app.route("/library")
    def library():
        return redirect("/search?lang=english", code=303)

    @app.route("/library/search")
    def library_search():
        query = (request.args.get("q") or "").strip()[:80]
        target = "/search?lang=english"
        if query:
            target += "&q=" + quote(query)
        return redirect(target, code=303)

    @app.route("/title/<kind>/<media_id>")
    def title(kind, media_id):
        kind = "series" if kind == "series" else "movie"
        media_id = (media_id or "").strip()[:40]
        if not re.match(r"^[A-Za-z0-9:]+$", media_id):
            return redirect("/search", code=303)

        try:
            item = stremio.meta(kind, media_id)
        except Exception:
            item = None
        if not item:
            return redirect("/search", code=303)

        season, episode = 1, 1
        seasons, by_season = [], {}
        if kind == "series":
            seasons = stremio.seasons(item) or [1]
            # Season 0 is the specials list, and no player has an episode to
            # play there. A show opened without ?s= therefore starts on its
            # first real season instead of on a page with no player at all.
            first = next((value for value in seasons if value > 0), seasons[0])
            season = _int_arg(request.args.get("s"), first)
            if season not in seasons:
                season = first
            by_season = {value: stremio.episodes_for(item, value)
                         for value in seasons}
            current = by_season.get(season) or []
            if current:
                episode = _int_arg(request.args.get("e"), current[0]["episode"])
                if not any(one["episode"] == episode for one in current):
                    episode = current[0]["episode"]

        _n, body, _l = views.title_page(item, season, episode, seasons,
                                        by_season)
        return render(item.get("name") or "Title", body)

    # ------------------------------------------------------------ einthusan
    def einthusan_item(media_id):
        """The Cinemeta record behind a media id, or None for a bad one."""
        media_id = (media_id or "").strip()[:40]
        if not re.match(r"^[A-Za-z0-9:]+$", media_id):
            return None
        try:
            return stremio.meta("movie", media_id)
        except Exception:
            return None

    @app.route("/einthusan/<media_id>")
    def einthusan_frame(media_id):
        """The frame for an Indian film.

        Einthusan signs a film per viewing instead of publishing an embed URL,
        and finding one means reading a few of its index pages, so the picker
        cannot hold a finished URL. This page paints at once and leaves the
        work to /api/einthusan, which answers with the signed mp4.
        """
        media_id = (media_id or "").strip()[:40]
        item = einthusan_item(media_id)
        if not item:
            return redirect("/search", code=303)

        heading = item.get("name") or "This film"
        start = max(0, _int_arg(request.args.get("t"), 0))
        if einthusan_source.offers("movie", item.get("country")):
            body = views.einthusan_player(heading, media_id, start)
        else:
            body = views.einthusan_missing(
                heading, "Einthusan carries Indian films, and Cinemeta "
                "does not list this one as Indian.")
        response = Response(body, mimetype="text/html; charset=utf-8")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/api/einthusan/<media_id>")
    def einthusan_stream(media_id):
        """The signed mp4 the einthusan frame plays.

        A signature belongs to one viewing and expires within hours, so this
        is answered fresh and never cached.
        """
        item = einthusan_item(media_id)
        if not item:
            return jsonify({"error": "This film is not in the library."}), 404
        if not einthusan_source.offers("movie", item.get("country")):
            return jsonify({"error": "Einthusan carries Indian films, and "
                                     "this one is not listed as Indian."})

        heading = item.get("name") or ""
        year = item.get("year")
        # Einthusan files a dub under an index of its own, and the index that
        # matched the title best is as often a dub as the original. The frame
        # plays the language the film was made in — the original index when
        # einthusan has one — and there is nothing to switch in the player.
        played = einthusan_source.play(heading, year)
        if not played:
            return jsonify({"error": "Einthusan has no playable copy of this "
                                     "film right now."})
        film = played["record"]
        code = played["code"]
        original = played["original"]
        found = einthusan_source.stream(film["id"])
        if not found:
            return jsonify({"error": "Einthusan's copy of this film will not "
                                     "play right now."})

        response = jsonify({
            "url": found["url"],
            "language": film.get("lang") or code.title(),
            "language_code": code,
            "original": original,
            "title": found.get("title") or heading,
            "expires": found.get("expires") or 0,
        })
        response.headers["Cache-Control"] = "no-store"
        return response

    # ---------------------------------------------------------------- status
    _status = {}

    @app.route("/api/up-next/<kind>/<media_id>")
    def up_next(kind, media_id):
        """What to watch after this one, for the row under a finished film.

        Nothing is stored: the title's first two genres are asked of the same
        catalogue the home page uses, and the title itself is dropped, so the
        answer is the shelf it belongs to rather than a recommendation engine.
        """
        kind = "series" if kind == "series" else "movie"
        if not re.match(r"^tt\d{5,}$", media_id or ""):
            return jsonify({"genre": "", "items": []}), 400

        item = stremio.meta(kind, media_id)
        if not item:
            return jsonify({"genre": "", "items": []})

        genres = [one for one in (item.get("genres") or []) if one][:2]
        items = []
        seen = {item.get("id")}
        for genre in genres:
            try:
                found = stremio.catalog(kind, "top", {"genre": genre})
            except Exception:
                continue
            for one in found:
                if one.get("id") in seen or not one.get("name"):
                    continue
                seen.add(one.get("id"))
                items.append({
                    "id": one["id"],
                    "type": kind,
                    "name": one.get("name") or "",
                    "year": str(one.get("year") or ""),
                    "poster": one.get("poster") or "",
                })
                if len(items) >= 12:
                    break
            if len(items) >= 12:
                break

        response = jsonify({"genre": genres[0] if genres else "", "items": items})
        response.headers["Cache-Control"] = "private, max-age=300"
        return response

    @app.route("/api/status")
    def status():
        """Whether each third-party player answers at all.

        A player is somebody else's site: when one stops answering there is
        nothing here to repair, but it is worth being able to see which one it
        is. Cached for five minutes, and never used to decide what to play.
        """
        now = time.time()
        hit = _status.get("value")
        if hit and now - hit["at"] < 300:
            return jsonify(hit["payload"])

        def probe(source):
            origin = source.get("origin") or ""
            if not origin:
                return {"key": source["key"], "ok": None, "ms": 0}
            started = time.time()
            try:
                with urllib.request.urlopen(origin, timeout=4) as response:
                    response.read(1)
                ok = True
            except urllib.error.HTTPError:
                # an answer is an answer: the host is up
                ok = True
            except Exception:
                ok = False
            return {"key": source["key"], "ok": ok,
                    "ms": int((time.time() - started) * 1000)}

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(probe, players.offered_sources()))
        payload = {"at": int(now), "sources": results}
        _status["value"] = {"at": now, "payload": payload}
        return jsonify(payload)

    # ---------------------------------------------------------------- misc
    @app.route("/healthz")
    def healthz():
        # A missing database must report itself, not take the endpoint down.
        # A missing database must report itself, not take the endpoint down.
        try:
            dialect = accounts._store().dialect
        except Exception:
            dialect = "unavailable"
        return {"ok": True, "groq": bool(os.environ.get("GROQ_API_KEY")),
                "database": dialect}

    @app.errorhandler(404)
    def not_found(_e):
        return redirect("/")

    return app
