from __future__ import annotations

import json
import mimetypes
import random
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import movie
import omdb_api

HOST = "127.0.0.1"
PORT = 5000
BASE_DIR = Path(__file__).resolve().parent
HTML_DIR = Path(movie.HTML_DIR).resolve()


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _user_payload(user_id: int, profile: dict) -> dict:
    return {
        "id": user_id,
        "name": profile.get("name", ""),
        "last_name": profile.get("last_name") or "",
        "display_name": movie._format_user_display(
            profile.get("name", ""),
            profile.get("last_name") or "",
        ),
    }


def _users_payload() -> dict:
    users = movie.movie_storage.get_users()
    items = [_user_payload(user_id, profile) for user_id, profile in users.items()]
    items.sort(key=lambda entry: (entry["display_name"].casefold(), int(entry["id"])))
    return {"users": items}


def _ensure_active_user() -> tuple[int, str]:
    try:
        return movie._get_active_user()
    except Exception:
        users = movie.movie_storage.get_users()
        if not users:
            raise RuntimeError("No users available.")

        chosen_user_id = None
        chosen_profile = None

        for user_id, profile in users.items():
            display_name = movie._format_user_display(
                profile.get("name", ""),
                profile.get("last_name") or "",
            )
            if display_name.casefold() == "default user":
                chosen_user_id = user_id
                chosen_profile = profile
                break

        if chosen_user_id is None:
            chosen_user_id = sorted(users)[0]
            chosen_profile = users[chosen_user_id]

        movie._set_active_user(
            chosen_user_id,
            chosen_profile.get("name", ""),
            chosen_profile.get("last_name") or "",
        )
        return movie._get_active_user()


def _active_user_payload() -> dict:
    user_id, _ = _ensure_active_user()
    users = movie.movie_storage.get_users()
    profile = users.get(user_id, {"name": "", "last_name": ""})
    return _user_payload(user_id, profile)


def _movie_payload(title: str, data: dict) -> dict:
    return {
        "title": title,
        "year": data.get("year"),
        "rating": data.get("rating"),
        "poster": data.get("poster"),
        "note": data.get("note"),
        "imdb_id": data.get("imdb_id"),
    }


def _movies_payload(user_id: int) -> dict:
    movies = movie.movie_storage.get_movies(user_id)
    return {"movies": [_movie_payload(title, data) for title, data in movies.items()]}


def _sorted_movies_payload(user_id: int, by: str) -> dict:
    movies = movie.movie_storage.get_movies(user_id)
    payload = [_movie_payload(title, data) for title, data in movies.items()]

    if by == "year":
        payload.sort(
            key=lambda entry: (
                entry.get("year") is None,
                -(int(entry.get("year") or 0)),
                entry["title"].casefold(),
            )
        )
    else:
        payload.sort(
            key=lambda entry: (
                entry.get("rating") is None,
                -(float(entry.get("rating") or 0)),
                entry["title"].casefold(),
            )
        )
    return {"movies": payload}


def _search_movies_payload(user_id: int, term: str) -> dict:
    search_term = term.casefold().strip()
    movies = movie.movie_storage.get_movies(user_id)
    matches = [
        _movie_payload(title, data)
        for title, data in movies.items()
        if search_term and search_term in title.casefold()
    ]
    return {"movies": matches}


def _filter_movies_payload(
    user_id: int,
    min_rating: float | None,
    start_year: int | None,
    end_year: int | None,
) -> dict:
    movies = movie.movie_storage.get_movies(user_id)
    filtered: list[dict] = []

    for title, data in movies.items():
        rating = data.get("rating")
        year = data.get("year")

        if min_rating is not None and (rating is None or float(rating) < min_rating):
            continue
        if start_year is not None and (year is None or int(year) < start_year):
            continue
        if end_year is not None and (year is None or int(year) > end_year):
            continue

        filtered.append(_movie_payload(title, data))

    return {"movies": filtered}


def _random_movie_payload(user_id: int) -> dict:
    movies = movie.movie_storage.get_movies(user_id)
    if not movies:
        return {"movie": None}
    title = random.choice(list(movies.keys()))
    return {"movie": _movie_payload(title, movies[title])}


def _stats_payload(user_id: int) -> dict:
    movies = movie.movie_storage.get_movies(user_id)
    if not movies:
        return {
            "stats": {
                "count": 0,
                "average_rating": 0,
                "median_rating": 0,
                "best_movie": None,
                "worst_movie": None,
            }
        }

    ratings = [float(data.get("rating") or 0) for data in movies.values() if data.get("rating") is not None]
    if not ratings:
        return {
            "stats": {
                "count": len(movies),
                "average_rating": 0,
                "median_rating": 0,
                "best_movie": None,
                "worst_movie": None,
            }
        }

    average_rating = sum(ratings) / len(ratings)
    sorted_ratings = sorted(ratings)
    length = len(sorted_ratings)
    if length % 2 == 1:
        median_rating = sorted_ratings[length // 2]
    else:
        median_rating = (sorted_ratings[length // 2 - 1] + sorted_ratings[length // 2]) / 2

    best_title = max(movies, key=lambda title: float(movies[title].get("rating") or 0))
    worst_title = min(movies, key=lambda title: float(movies[title].get("rating") or 0))

    return {
        "stats": {
            "count": len(movies),
            "average_rating": average_rating,
            "median_rating": median_rating,
            "best_movie": _movie_payload(best_title, movies[best_title]),
            "worst_movie": _movie_payload(worst_title, movies[worst_title]),
        }
    }


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        return {}
    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}
    return json.loads(raw_body.decode("utf-8"))


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = _json_bytes(payload)
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_bytes(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _safe_static_path(request_path: str) -> Path | None:
    clean_path = request_path.lstrip("/")
    if not clean_path:
        return None

    candidates = [HTML_DIR / clean_path, BASE_DIR / clean_path]

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            continue

        if not resolved.is_file():
            continue

        if resolved.is_relative_to(HTML_DIR) or resolved.is_relative_to(BASE_DIR):
            return resolved

    return None


def _serve_static_file(handler: BaseHTTPRequestHandler, path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    content_type, _ = mimetypes.guess_type(path.name)
    if not content_type:
        content_type = "application/octet-stream"
    if content_type.startswith("text/") and "charset" not in content_type:
        content_type = f"{content_type}; charset=utf-8"
    body = path.read_bytes()
    _send_bytes(handler, HTTPStatus.OK, body, content_type)
    return True


class MovieApiHandler(BaseHTTPRequestHandler):
    server_version = "MovieApiServer/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route in {"/", "/movies.html", "/index.html"}:
            movie.generate_website()
            html_file = movie.WEBSITE_FILE if movie.WEBSITE_FILE.exists() else HTML_DIR / "movies.html"
            if not _serve_static_file(self, html_file):
                _send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Website file not found."})
            return

        if route.startswith("/api/"):
            self._handle_api_get(route, query)
            return

        static_file = _safe_static_path(route)
        if static_file and _serve_static_file(self, static_file):
            return

        _send_json(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path

        if not route.startswith("/api/"):
            _send_json(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        try:
            payload = _read_json_body(self)
        except json.JSONDecodeError:
            _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return

        try:
            self._handle_api_post(route, payload)
        except ValueError as exc:
            _send_json(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except omdb_api.OMDbAPIError as exc:
            _send_json(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except RuntimeError as exc:
            _send_json(self, HTTPStatus.CONFLICT, {"error": str(exc)})

    def _handle_api_get(self, route: str, query: dict[str, list[str]]) -> None:
        user_id, _ = _ensure_active_user()

        if route == "/api/users":
            _send_json(self, HTTPStatus.OK, _users_payload())
            return

        if route == "/api/users/active":
            _send_json(self, HTTPStatus.OK, _active_user_payload())
            return

        if route == "/api/movies":
            _send_json(self, HTTPStatus.OK, _movies_payload(user_id))
            return

        if route == "/api/movies/sorted":
            sort_by = (query.get("by", ["rating"])[0] or "rating").strip().lower()
            if sort_by not in {"rating", "year"}:
                _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid sort field."})
                return
            _send_json(self, HTTPStatus.OK, _sorted_movies_payload(user_id, sort_by))
            return

        if route == "/api/movies/histogram":
            _send_json(self, HTTPStatus.OK, _sorted_movies_payload(user_id, "rating"))
            return

        if route == "/api/movies/random":
            _send_json(self, HTTPStatus.OK, _random_movie_payload(user_id))
            return

        if route == "/api/movies/stats":
            _send_json(self, HTTPStatus.OK, _stats_payload(user_id))
            return

        if route == "/api/movies/search":
            term = unquote(query.get("term", [""])[0])
            _send_json(self, HTTPStatus.OK, _search_movies_payload(user_id, term))
            return

        if route == "/api/movies/filter":
            def _parse_float(value: str | None) -> float | None:
                if value is None or value == "":
                    return None
                return float(value)

            def _parse_int(value: str | None) -> int | None:
                if value is None or value == "":
                    return None
                return int(value)

            try:
                min_rating = _parse_float(query.get("min_rating", [None])[0])
                start_year = _parse_int(query.get("start_year", [None])[0])
                end_year = _parse_int(query.get("end_year", [None])[0])
            except ValueError:
                _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid filter values."})
                return

            _send_json(
                self,
                HTTPStatus.OK,
                _filter_movies_payload(user_id, min_rating, start_year, end_year),
            )
            return

        _send_json(self, HTTPStatus.NOT_FOUND, {"error": "Unknown API endpoint."})

    def _handle_api_post(self, route: str, payload: dict) -> None:
        if route == "/api/users":
            name = str(payload.get("name", "")).strip()
            last_name = str(payload.get("last_name", "")).strip()
            if not name:
                raise ValueError("User name cannot be empty.")
            user_id = movie.movie_storage.get_user_id_or_create(name, last_name)
            movie._set_active_user(user_id, name, last_name)
            movie.generate_website()
            _send_json(self, HTTPStatus.OK, _active_user_payload())
            return

        if route == "/api/users/active":
            user_id_value = payload.get("id")
            if user_id_value is None:
                raise ValueError("Missing user id.")
            user_id = int(user_id_value)
            users = movie.movie_storage.get_users()
            profile = users.get(user_id)
            if profile is None:
                raise ValueError("User not found.")
            movie._set_active_user(user_id, profile.get("name", ""), profile.get("last_name") or "")
            movie.generate_website()
            _send_json(self, HTTPStatus.OK, _active_user_payload())
            return

        user_id, _ = _ensure_active_user()

        if route == "/api/movies/add":
            movie_name = str(payload.get("title", "")).strip()
            if not movie_name:
                raise ValueError("Movie title cannot be empty.")

            current_movies = movie.movie_storage.get_movies(user_id)
            if movie_name in current_movies:
                raise RuntimeError("Movie already exists.")

            movie_data = omdb_api.get_movie_for_storage(movie_name)
            stored_title = movie_data["title"]
            if stored_title in current_movies:
                raise RuntimeError(f"Movie '{stored_title}' already exists.")

            success = movie.movie_storage.add_movie(
                stored_title,
                movie_data["year"],
                movie_data["rating"],
                user_id,
                movie_data.get("poster"),
                imdb_id=movie_data.get("imdb_id"),
            )
            if not success:
                raise RuntimeError("Could not add movie.")

            movie.generate_website()
            _send_json(self, HTTPStatus.OK, {"movie": _movie_payload(stored_title, movie_data)})
            return

        if route == "/api/movies/delete":
            movie_name = str(payload.get("title", "")).strip()
            if not movie_name:
                raise ValueError("Movie title cannot be empty.")
            deleted = movie.movie_storage.delete_movie(movie_name, user_id)
            movie.generate_website()
            if not deleted:
                raise RuntimeError("Movie not found.")
            _send_json(self, HTTPStatus.OK, {"deleted": True})
            return

        if route == "/api/movies/update":
            movie_name = str(payload.get("title", "")).strip()
            if not movie_name:
                raise ValueError("Movie title cannot be empty.")

            updated = movie.movie_storage.update_movie(
                movie_name,
                rating=payload.get("rating"),
                year=payload.get("year"),
                poster=payload.get("poster"),
                note=payload.get("note"),
                imdb_id=payload.get("imdb_id"),
                user_id=user_id,
            )
            movie.generate_website()
            if not updated:
                raise RuntimeError("Movie not found.")
            _send_json(self, HTTPStatus.OK, {"updated": True})
            return

        raise RuntimeError("Unknown API endpoint.")


def main() -> None:
    _ensure_active_user()
    movie.generate_website()
    server = ThreadingHTTPServer((HOST, PORT), MovieApiHandler)
    print(f"Serving on http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
