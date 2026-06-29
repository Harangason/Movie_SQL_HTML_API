"""
Small interface module for the OMDb API.

Set your API key before using this module:
PowerShell:
    $env:OMDB_API_KEY = "your_api_key_here"

The functions in this file only send read-only GET requests to OMDb. They keep
all website/API communication separate from the storage layer and the terminal UI.
"""

import os
from pathlib import Path
from typing import Any

import requests

API_KEY_ENV = "OMDB_API_KEY"
API_KEY_FILES = [
    Path(r"H:\OneDrive\AI_with_Python\Masterschool\OMDB_API_KEY.env"),
]
DATA_API_URL = "http://www.omdbapi.com/"
POSTER_API_URL = "http://img.omdbapi.com/"
REQUEST_TIMEOUT_SECONDS = 10


class OMDbAPIError(Exception):
    """Raised when OMDb cannot return the requested movie data."""


def _get_api_key(api_key: str | None = None) -> str:
    """Return the explicit API key, environment key, or key from a local file."""
    resolved_api_key = api_key or os.getenv(API_KEY_ENV) or _read_api_key_file()

    if not resolved_api_key:
        raise OMDbAPIError(
            f"Missing OMDb API key. Set $env:{API_KEY_ENV} or create {API_KEY_FILES[-1]}."
        )

    return resolved_api_key


def _read_api_key_file() -> str | None:
    """Read the OMDb API key from a local key file, if one exists."""
    for api_key_file in API_KEY_FILES:
        if not api_key_file.exists():
            continue

        content = api_key_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        if "=" in content:
            key_name, key_value = content.split("=", 1)
            if key_name.strip() == API_KEY_ENV:
                return key_value.strip().strip('"').strip("'")
            continue

        return content.strip('"').strip("'")

    return None


def _request_data(params: dict[str, Any], api_key: str | None = None) -> dict[str, Any]:
    """Send a request to the OMDb data API and return the JSON response."""
    request_params = {
        "apikey": _get_api_key(api_key),
        **params,
    }

    try:
        response = requests.get(
            DATA_API_URL,
            params=request_params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise OMDbAPIError(f"OMDb request failed: {error}") from error

    data = response.json()

    if data.get("Response") == "False":
        raise OMDbAPIError(data.get("Error", "OMDb returned an unknown error."))

    return data


def search_movies(query: str, page: int = 1, api_key: str | None = None) -> list[dict[str, Any]]:
    """Search OMDb by movie title and return matching results."""
    data = _request_data(
        {
            "s": query,
            "page": page,
            "type": "movie",
        },
        api_key=api_key,
    )

    return data.get("Search", [])


def get_movie_by_title(
    title: str,
    year: int | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Retrieve detailed movie data from OMDb by title."""
    params: dict[str, Any] = {
        "t": title,
        "type": "movie",
        "plot": "short",
    }

    if year is not None:
        params["y"] = year

    return _request_data(params, api_key=api_key)


def get_movie_by_id(imdb_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Retrieve detailed movie data from OMDb by IMDb id."""
    return _request_data(
        {
            "i": imdb_id,
            "plot": "short",
        },
        api_key=api_key,
    )


def get_poster_url(imdb_id: str, api_key: str | None = None) -> str:
    """Build the OMDb poster API URL for an IMDb id."""
    return f"{POSTER_API_URL}?apikey={_get_api_key(api_key)}&i={imdb_id}"


def get_movie_for_storage(title: str, api_key: str | None = None) -> dict[str, Any]:
    """
    Retrieve one movie and normalize it for movie_storage_sql.add_movie().

    Returns:
        {
            "title": "Inception",
            "year": 2010,
            "rating": 8.8,
            "imdb_id": "tt1375666",
            "poster": "https://..."
        }
    """
    movie = get_movie_by_title(title, api_key=api_key)

    return {
        "title": movie["Title"],
        "year": int(movie["Year"][:4]),
        "rating": _parse_rating(movie.get("imdbRating")),
        "imdb_id": movie.get("imdbID"),
        "poster": _parse_poster_url(movie.get("Poster")),
    }


def _parse_rating(rating: str | None) -> float:
    """Convert an OMDb IMDb rating value into a float."""
    if not rating or rating == "N/A":
        return 0.0

    return float(rating)


def _parse_poster_url(poster: str | None) -> str:
    """Return a usable poster URL or N/A if OMDb has no poster."""
    if not poster or poster == "N/A":
        return "N/A"

    return poster
