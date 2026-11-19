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
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import quote

from flask import Flask, Response, jsonify, redirect, request

from . import accounts
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
                                   httponly=True, samesite="Lax")
        else:
            response = redirect("/settings", code=303)
            response.set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                httponly=True, samesite="Lax")
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
                                   httponly=True, samesite="Lax")
        else:
            response = redirect("/settings", code=303)
            response.set_cookie(SESSION_COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                                httponly=True, samesite="Lax")
        return response

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
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
