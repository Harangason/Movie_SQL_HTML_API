"""
Movie database system using movie_storage_sql.py for SQLite persistence.

Interactive movie database application that uses movie_storage_sql.py for
SQLAlchemy-based data persistence. Provides a terminal menu to list, add, delete, update, search,
and analyze movies. Includes fuzzy search, statistics, sorting, and rating
histogram visualization.
Features:
- List all movies with ratings and years.
- Add new movies with name, rating, and year.
- Delete movies by name.
- Update movie ratings.
- Search movies by name with exact, partial, and fuzzy matching.
- Show statistics: average, median, best/worst movies.
- Pick a random movie.
- Sort movies by rating or year.
- Create a bar chart of movie ratings.
- Manage multiple user profiles with per-user movie collections.
Designed for simplicity and user-friendliness with colored terminal output.
"""

from datetime import datetime
from difflib import get_close_matches
from html import escape
from pathlib import Path
import importlib.util
import random
import re
import os
import sys
import webbrowser
from urllib.parse import quote
import warnings

try:
    from fuzzywuzzy import process
except ModuleNotFoundError:
    process = None

warnings.filterwarnings(
    "ignore",
    message="Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning",
    category=UserWarning,
)


BASE_DIR = Path(__file__).resolve().parent

# Support both old and moved project layouts:
# 1) flat:
#    - movie.py, movie_storage_sql.py, HTML/
# 2) moved:
#    - movie.py, omdb_api.py, and nested Movie_SQL_HTML_API/
#      ├── movie_storage/movie_storage_sql.py
#      └── HTML/
PROJECT_ROOT = BASE_DIR / "Movie_SQL_HTML_API"
HTML_DIR = BASE_DIR / "HTML"
MOVIE_STORAGE_DIR = BASE_DIR / "movie_storage"

if not HTML_DIR.is_dir() and (PROJECT_ROOT / "HTML").is_dir():
    HTML_DIR = PROJECT_ROOT / "HTML"
if not MOVIE_STORAGE_DIR.is_dir() and (PROJECT_ROOT / "movie_storage").is_dir():
    MOVIE_STORAGE_DIR = PROJECT_ROOT / "movie_storage"

TEMPLATE_FILE = HTML_DIR / "index_template.html"
WEBSITE_FILE = HTML_DIR / "movies.html"
APP_TITLE = "My Movie App"


def _load_movie_storage_module():
    possible_paths = [
        BASE_DIR / "movie_storage_sql.py",
        BASE_DIR / "movie_storage" / "movie_storage_sql.py",
        MOVIE_STORAGE_DIR / "movie_storage_sql.py",
    ]

    for module_path in possible_paths:
        if module_path.exists():
            spec = importlib.util.spec_from_file_location(
                "movie_storage",
                module_path,
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            return module

    raise ModuleNotFoundError(
        "movie_storage_sql.py not found. Expected one of:\n"
        f"- {BASE_DIR / 'movie_storage_sql.py'}\n"
        f"- {BASE_DIR / 'movie_storage' / 'movie_storage_sql.py'}\n"
        f"- {MOVIE_STORAGE_DIR / 'movie_storage_sql.py'}"
    )


movie_storage = _load_movie_storage_module()
import omdb_api


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def error(msg):
    print(f"{Colors.RED}Error: {msg}{Colors.END}")


def info(msg):
    print(f"{Colors.BLUE}{msg}{Colors.END}")


def user_input(prompt):
    return input(f"{Colors.GREEN}{prompt}{Colors.END}")


_ACTIVE_USER_ID: int | None = None
_ACTIVE_USER_NAME: str | None = None
_ACTIVE_USER_LAST_NAME: str | None = None


def _set_active_user(user_id: int, user_name: str, user_last_name: str = "") -> None:
    global _ACTIVE_USER_ID, _ACTIVE_USER_NAME, _ACTIVE_USER_LAST_NAME
    _ACTIVE_USER_ID = user_id
    _ACTIVE_USER_NAME = user_name
    _ACTIVE_USER_LAST_NAME = user_last_name or ""
    display_name = _format_user_display(user_name, _ACTIVE_USER_LAST_NAME)
    info(f"Welcome back, {display_name}! 🎬")


def _get_active_user() -> tuple[int, str]:
    if _ACTIVE_USER_ID is None or _ACTIVE_USER_NAME is None:
        raise RuntimeError("No active user selected.")

    return _ACTIVE_USER_ID, _format_user_display(_ACTIVE_USER_NAME, _ACTIVE_USER_LAST_NAME)


def _format_user_display(name: str, last_name: str | None) -> str:
    return f"{name} {last_name}".strip() if last_name else name

def format_poster(poster: str | None) -> str:
    if not poster or poster == "N/A":
        return "No poster available"

    return poster

def sanitize_filename(value: str) -> str:
    """Create a safe file name for HTML output."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe or "user"


def sync_missing_movie_data(user_id: int) -> None:
    """Automatically enrich old database entries with OMDb data."""
    movies = movie_storage.get_movies(user_id)
    movies_without_poster = [title for title, data in movies.items() if not data.get("poster")]

    if not movies_without_poster:
        return

    updated_count = 0
    failed_titles = []

    for title in movies_without_poster:
        try:
            movie_data = omdb_api.get_movie_for_storage(title)
        except omdb_api.OMDbAPIError:
            failed_titles.append(title)
            continue

        if movie_storage.update_movie(
            title,
            rating=movie_data["rating"],
            year=movie_data["year"],
            poster=movie_data["poster"],
            imdb_id=movie_data.get("imdb_id"),
            user_id=user_id,
        ):
            updated_count += 1

    if updated_count:
        info(f"Updated {updated_count} old movie record(s) with OMDb data.")

    if failed_titles:
        info(f"Could not update {len(failed_titles)} old movie record(s) from OMDb.")


def suggest_similar_movies(movie_name: str, movies: dict) -> list[str]:
    """Returns top 3 fuzzy suggestions."""
    titles = list(movies.keys())

    if process is None:
        return get_close_matches(movie_name, titles, n=3, cutoff=0.6)

    suggestions = process.extract(movie_name, titles, limit=3)
    return [title for title, score in suggestions if score > 60]


def select_movie_name(movies: dict, prompt: str = "Enter movie name: ") -> str | None:
    user_input_name = user_input(prompt).strip()

    if not user_input_name:
        error("Movie name cannot be empty")
        return None

    name_lower = user_input_name.lower()

    if user_input_name in movies:
        return user_input_name

    partial_matches = [title for title in movies if name_lower in title.lower()]

    if len(partial_matches) == 1:
        return partial_matches[0]

    if partial_matches:
        info(f"\nFound matches for '{user_input_name}':")
        for i, title in enumerate(partial_matches, 1):
            info(f"{i}. {title}")

        choice = user_input("Choose number or press Enter to use your input: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(partial_matches):
                return partial_matches[idx - 1]

        return user_input_name

    suggestions = suggest_similar_movies(user_input_name, movies)

    if len(suggestions) == 1:
        return suggestions[0]

    if suggestions:
        info(f"\nSimilar movies:")
        for i, title in enumerate(suggestions, 1):
            info(f"{i}. {title}")

        choice = user_input("Choose number or press Enter to use your input: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(suggestions):
                return suggestions[idx - 1]

        return user_input_name

    error("No similar movies found.")
    return user_input_name


def select_user() -> None:
    """Ask user to choose an existing profile or create a new one."""
    while True:
        users = movie_storage.get_users()
        user_pairs = list(users.items())

        print(f"{Colors.CYAN}\nSelect a user:{Colors.END}")
        for index, (user_id, profile) in enumerate(user_pairs, start=1):
            display_name = _format_user_display(profile["name"], profile.get("last_name") or "")
            print(f"{Colors.CYAN}{index}. {display_name}{Colors.END}")
        print(f"{Colors.CYAN}{len(user_pairs) + 1}. Create new user{Colors.END}")

        choice_input = user_input("\nEnter choice: ").strip()
        if not choice_input.isdigit():
            error("Enter a valid number.")
            continue

        choice = int(choice_input)
        if 1 <= choice <= len(user_pairs):
            user_id, profile = user_pairs[choice - 1]
            _set_active_user(
                user_id,
                profile["name"],
                profile.get("last_name") or "",
            )
            return

        if choice == len(user_pairs) + 1:
            new_user_name = user_input("Enter new user first name: ").strip()
            if not new_user_name:
                error("User name cannot be empty.")
                continue
            new_user_last_name = user_input("Enter new user last name (optional): ").strip()
            if not new_user_last_name:
                new_user_last_name = ""

            new_user_id = movie_storage.get_user_id_or_create(
                new_user_name,
                new_user_last_name,
            )
            _set_active_user(new_user_id, new_user_name.strip(), new_user_last_name)
            info(
                f"Created new user: {_format_user_display(new_user_name, new_user_last_name)}"
            )
            return

        error("Invalid choice.")


def switch_user() -> None:
    select_user()
    sync_missing_movie_data(_get_active_user()[0])


# ---------------------------------------------------------
# MOVIE FUNCTIONS
# ---------------------------------------------------------

def movie_list():
    """Prints all movies of active user."""
    user_id, user_name = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    if not movies:
        error(f"{user_name}, your movie collection is empty. Add some movies!")
        return

    info(f"\n{len(movies)} movies in total")
    for title, data in movies.items():
        year = data.get("year", "unknown")
        rating = data.get("rating", 0)
        note = data.get("note")
        poster = format_poster(data.get("poster"))
        info(f"{title} ({year}): {rating}")
        if note:
            info(f"Note: {note}")
        info(f"Poster: {poster}")


def _build_user_cards(active_user_id: int, users: dict[int, dict[str, str | None]]) -> str:
    """Build clickable user cards for the HTML user chooser."""
    default_user_id = None
    ordered_users = []

    for user_id, profile in users.items():
        display_name = _format_user_display(profile["name"], profile.get("last_name") or "")
        if (
            display_name.lower() == "default user"
            or (
                profile.get("name", "").strip().lower() == "default"
                and (profile.get("last_name") or "").strip().lower() == "user"
            )
        ):
            default_user_id = user_id
            continue

        ordered_users.append((display_name, user_id, profile))

    ordered_users.sort(key=lambda item: item[0].lower())

    if default_user_id is not None and default_user_id in users:
        default_profile = users[default_user_id]
        ordered_users.append(
            (
                "Default User",
                default_user_id,
                default_profile,
            )
        )

    cards = []

    for display_name, user_id, profile in ordered_users:
        safe_name = escape(display_name)
        selected_class = " user-card selected" if user_id == active_user_id else ""
        cards.append(
            '        <button type="button"'
            f' class="user-card{selected_class}" data-user-id="{user_id}"'
            f' data-user-name="{safe_name}">'
            f'{safe_name}'
            "</button>"
        )

    cards.append(
        '        <button type="button" class="user-card user-card-new"'
        ' data-action="create-user">'
        "Create new user"
        "</button>"
    )

    return "\n".join(cards)


def _build_cli_sidebar() -> str:
    """Build a static CLI-style menu block for the HTML left column."""
    options = [
        ("1", "List movies"),
        ("2", "Add movie"),
        ("3", "Delete movie"),
        ("4", "Update movie"),
        ("5", "Stats"),
        ("6", "Random movie"),
        ("7", "Search movie"),
        ("8", "Movies sorted by rating"),
        ("9", "Movies sorted by year"),
        ("10", "Create Rating Histogram"),
        ("11", "Filter movies"),
        ("12", "Switch user"),
    ]

    return "\n".join(
        f'        <li><button type="button" class="cli-option"'
        f' data-cli-choice="{choice}" data-cli-label="{escape(f"{choice}. {label}")}">'
        f"{choice}. {escape(label)}</button></li>"
        for choice, label in options
    )


def _build_cli_action_cards() -> str:
    """Build action cards for the center panel after clicking a CLI action."""
    action_queries = [
        ("1", "List movies"),
        ("2", "Add movie"),
        ("3", "Delete movie"),
        ("4", "Update movie"),
        ("5", "Stats"),
        ("6", "Random movie"),
        ("7", "Search movie"),
        ("8", "Movies sorted by rating"),
        ("9", "Movies sorted by year"),
        ("10", "Create Rating Histogram"),
        ("11", "Filter movies"),
        ("12", "Switch user"),
    ]

    action_prompts = {
        "1": "In der CLI: Gib als nächste Eingabe 1 ein, um die Filme anzuzeigen.",
        "2": "In der CLI: Gib als nächste Eingabe 2 ein, dann 'Enter movie name'.",
        "3": "In der CLI: Gib als nächste Eingabe 3 ein, dann 'Enter movie name to delete'.",
        "4": "In der CLI: Gib als nächste Eingabe 4 ein, dann 'Enter movie name' und 'Enter movie note'.",
        "5": "In der CLI: Gib als nächste Eingabe 5 ein, um Statistiken zu sehen.",
        "6": "In der CLI: Gib als nächste Eingabe 6 ein, um einen zufälligen Film zu laden.",
        "7": "In der CLI: Gib als nächste Eingabe 7 ein, dann 'Enter part of movie name'.",
        "8": "In der CLI: Gib als nächste Eingabe 8 ein, um nach Bewertung zu sortieren.",
        "9": "In der CLI: Gib als nächste Eingabe 9 ein, um nach Jahr zu sortieren.",
        "10": "In der CLI: Gib als nächste Eingabe 10 ein, um ein Bewertungs-Histogramm zu erstellen.",
        "11": "In der CLI: Gib als nächste Eingabe 11 ein, dann Filterwerte eingeben.",
        "12": "In der CLI: Gib als nächste Eingabe 12 ein, um Nutzer zu wechseln.",
    }

    return "\n".join(
        '<button type="button" class="action-card" '
        f'data-action-choice="{choice}" data-action-prompt="{escape(action_prompts.get(choice, ""))}"'
        f'>{escape(f"{choice}. {label}")}</button>'
        for choice, label in action_queries
    )


def add_movie():
    """Adds a new movie with title, year, rating, and poster URL from OMDb."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)
    new_movie_name = user_input("Enter movie name: ").strip()

    if not new_movie_name:
        error("Movie name cannot be empty")
        return

    if new_movie_name in movies:
        info("Movie already exists.")
        return

    try:
        movie_data = omdb_api.get_movie_for_storage(new_movie_name)
    except omdb_api.OMDbAPIError as api_error:
        error(api_error)
        return

    title = movie_data["title"]
    if title in movies:
        info(f"Movie '{title}' already exists.")
        return

    if movie_storage.add_movie(
        title,
        movie_data["year"],
        movie_data["rating"],
        user_id,
        movie_data["poster"],
        imdb_id=movie_data.get("imdb_id"),
    ):
        info(f"Movie '{title}' added to your collection.")
        info(f"Year: {movie_data['year']}")
        info(f"Rating: {movie_data['rating']}")
        info(f"Poster: {format_poster(movie_data['poster'])}")


def delete_movie():
    """Deletes a movie."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)
    movie_name = select_movie_name(movies, "Enter movie name to delete: ")

    if movie_name and movie_storage.delete_movie(movie_name, user_id):
        info(f"Movie '{movie_name}' deleted.")
    else:
        error("Movie not found.")


def update_movie(movie_name: str = None):
    """Updates a movie with a user note."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    if movie_name is None:
        movie_name = select_movie_name(movies, "Enter movie name: ")

    if movie_name not in movies:
        error("Movie not found.")
        return

    movie_note = user_input("Enter movie note: ").strip()

    if movie_storage.update_movie(movie_name, note=movie_note, user_id=user_id):
        info(f"Movie '{movie_name}' updated.")
    else:
        error("Update failed.")


def search_movie():
    """Searches for a movie."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)
    movie_name = select_movie_name(movies, "Enter part of movie name: ")

    if movie_name and movie_name in movies:
        data = movies[movie_name]
        poster = format_poster(data.get("poster"))
        info(f"{movie_name}: Rating: {data.get('rating')}, Year: {data.get('year')}")
        note = data.get("note")
        if note:
            info(f"Note: {note}")
        info(f"Poster: {poster}")
    else:
        error("Movie not found.")


# ---------------------------------------------------------
# STATS
# ---------------------------------------------------------

def stats_movies():
    """Shows statistics."""
    user_id, user_name = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    if not movies:
        error(f"No movies available for {user_name}.")
        return

    ratings = [m["rating"] for m in movies.values()]
    avg = sum(ratings) / len(ratings)

    sorted_ratings = sorted(ratings)
    length = len(sorted_ratings)
    if length % 2 == 1:
        median = sorted_ratings[length // 2]
    else:
        median = (sorted_ratings[length // 2 - 1] + sorted_ratings[length // 2]) / 2

    best = max(movies, key=lambda m: movies[m]["rating"])
    worst = min(movies, key=lambda m: movies[m]["rating"])

    info(
        f"Average rating: {avg:.2f}\n"
        f"Median rating: {median}\n"
        f"Best movie: {best}, {movies[best]['rating']}\n"
        f"Worst movie: {worst}, {movies[worst]['rating']}"
    )


def random_movie():
    """Picks a random movie."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    if not movies:
        error("No movies available.")
        return

    movie = random.choice(list(movies.keys()))
    info(f"\nYour movie for tonight: {movie}, rated {movies[movie]['rating']}")


def movies_sorted_by_rating():
    """Lists movies sorted by rating (descending)."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)
    sorted_list = sorted(movies.items(), key=lambda item: item[1]["rating"], reverse=True)

    for title, data in sorted_list:
        info(f"{title}: {data['rating']}")


def movies_sorted_by_year():
    """Lists movies sorted by year (descending)."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    sorted_list = sorted(
        movies.items(),
        key=lambda item: int(item[1]["year"]),
        reverse=True,
    )

    for title, data in sorted_list:
        info(f"{title}: {data['year']}")


def add_timestamps_to_movies(movies):
    """Add Unix timestamp to all movies for convenience."""
    for title, data in movies.items():
        date_obj = datetime(int(data["year"]), 1, 1)
        timestamp = int(date_obj.timestamp())
        data["timestamp"] = timestamp

    return movies


def filter_movies():
    """Filters movies based on min rating and a year range."""
    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)

    min_rate_input = user_input("Enter minimum rating (leave blank for no minimum rating): ").strip()
    start_year_input = user_input("Enter start year (leave blank for no start year): ").strip()
    end_year_input = user_input("Enter end year (leave blank for no end year): ").strip()

    filtered_movies = {}

    for title, data in movies.items():
        if min_rate_input and data["rating"] < float(min_rate_input):
            continue

        movie_year = int(data["year"])
        if start_year_input and movie_year < int(start_year_input):
            continue
        if end_year_input and movie_year > int(end_year_input):
            continue

        filtered_movies[title] = data

    if not filtered_movies:
        info("No movies found matching the criteria.")
        return

    info("\nMatching movies:")
    for title, data in filtered_movies.items():
        info(f"- {title} ({data['year']}): Rating {data['rating']}")


def create_rating_histogram():
    """Creates a bar chart of movie ratings."""
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        error("matplotlib is not installed. Install it to create rating histograms.")
        return

    user_id, _ = _get_active_user()
    movies = movie_storage.get_movies(user_id)
    if not movies:
        error("No movies available.")
        return

    sorted_movies = sorted(movies.items(), key=lambda item: item[1]["rating"], reverse=True)
    movies_per_page = 25
    total_pages = (len(sorted_movies) + movies_per_page - 1) // movies_per_page

    for page_number in range(total_pages):
        start = page_number * movies_per_page
        end = start + movies_per_page
        page_movies = sorted_movies[start:end]

        titles = [title for title, _ in page_movies]
        ratings = [data["rating"] for _, data in page_movies]
        x_positions = range(len(titles))

        plt.figure(figsize=(14, 7))
        plt.bar(x_positions, ratings, width=0.65, color="skyblue", edgecolor="black")
        plt.xticks(x_positions, titles, rotation=45, ha="right")
        plt.xlim(-0.5, movies_per_page - 0.5)
        plt.ylim(0, 10)
        plt.xlabel("Movie Title")
        plt.ylabel("Rating")
        plt.title(f"Movie Ratings ({page_number + 1}/{total_pages})")
        plt.tight_layout()

    plt.show()


def generate_movie_grid(movies: dict) -> str:
    """Generate the HTML grid items for all movies."""
    def _build_imdb_link(imdb_id: str | None, title: str) -> str:
        if imdb_id:
            return f"https://www.imdb.com/title/{imdb_id}/"

        safe_query = quote(title)
        return f"https://www.imdb.com/find/?q={safe_query}&ref_=nv_sr_fn"

    def _build_rating_stars(rating: float | int | None) -> str:
        if rating is None:
            return (
                '<div class="movie-rating-stars" aria-label="Rating not available">'
                '<span class="star empty">&#9734;&#9734;&#9734;&#9734;&#9734;</span>'
                "</div>"
            )

        try:
            normalized = round(float(rating), 1)
        except (TypeError, ValueError):
            return (
                '<div class="movie-rating-stars" aria-label="Rating not available">'
                '<span class="star empty">&#9734;&#9734;&#9734;&#9734;&#9734;</span>'
                "</div>"
            )

        normalized = max(0.0, min(10.0, normalized))
        filled_stars = int((normalized / 2) + 0.5)
        star_spans = "".join(
            '<span class="star'
            f'{ " filled" if index < filled_stars else " empty"}">'
            f'{"&#9733;" if index < filled_stars else "&#9734;"}</span>'
            for index in range(5)
        )

        return (
            f'<div class="movie-rating-stars" aria-label="Rating {normalized} out of 10">'
            f"{star_spans}"
            f'<span class="rating-value">{normalized:.1f}</span>'
            "</div>"
        )

    movie_items = []

    for title, data in movies.items():
        safe_title = escape(title)
        safe_year = escape(str(data.get("year", "unknown")))
        note = data.get("note") or ""
        safe_note = escape(note)
        safe_note_attr = escape(note, quote=True)
        rating_stars = _build_rating_stars(data.get("rating"))
        poster = data.get("poster")
        imdb_link = _build_imdb_link(data.get("imdb_id"), title)
        safe_imdb_link = escape(imdb_link, quote=True)
        poster_html = '<div class="movie-poster-wrap">'
        poster_html += f'<a class="movie-poster-link" href="{safe_imdb_link}" target="_blank" rel="noopener noreferrer">'

        if poster and poster != "N/A":
            safe_poster = escape(poster, quote=True)
            poster_html += (
                f'<img class="movie-poster" src="{safe_poster}" '
                f'alt="{safe_title} poster" '
                f'data-note="{safe_note_attr}"/>'
            )
        else:
            poster_html += f'<div class="movie-poster" data-note="{safe_note_attr}"></div>'

        poster_html += "</a>"

        if note:
            poster_html += f'<span class="movie-note">{safe_note}</span>'

        poster_html += "</div>"
        movie_items.append(
            "            <li>\n"
            '                <div class="movie">\n'
            f"                    {rating_stars}\n"
            f"                    {poster_html}\n"
            f'                    <div class="movie-title">{safe_title}</div>\n'
            f'                    <div class="movie-year">{safe_year}</div>\n'
            "                </div>\n"
            "            </li>"
        )

    return "\n".join(movie_items)


def generate_website():
    """Generate HTML output from the movie database."""
    if not TEMPLATE_FILE.exists():
        error(f"Template file not found: {TEMPLATE_FILE.name}")
        return False

    user_id, user_name = _get_active_user()
    users = movie_storage.get_users()
    movies = movie_storage.get_movies(user_id)
    movie_grid = generate_movie_grid(movies)
    user_cards = _build_user_cards(user_id, users)
    cli_sidebar = _build_cli_sidebar()
    cli_action_cards = _build_cli_action_cards()

    website_html = TEMPLATE_FILE.read_text(encoding="utf-8")
    website_html = website_html.replace("__TEMPLATE_TITLE__", escape(f"{APP_TITLE}"))
    website_html = website_html.replace("__TEMPLATE_USER_NAME__", escape(user_name))
    website_html = website_html.replace("__TEMPLATE_USER_CARDS__", user_cards)
    website_html = website_html.replace("__TEMPLATE_CLI_MENU__", cli_sidebar)
    website_html = website_html.replace("__TEMPLATE_CLI_ACTION_CARDS__", cli_action_cards)
    website_html = website_html.replace("__TEMPLATE_MOVIE_GRID__", movie_grid)

    with open(WEBSITE_FILE, "w", encoding="utf-8") as output_file:
        output_file.write(website_html)
        output_file.flush()
        os.fsync(output_file.fileno())

    info(f"Website generated successfully as {WEBSITE_FILE.name}")
    return True


def open_generated_website() -> bool:
    """Open the generated HTML website in the default browser."""
    if not WEBSITE_FILE.exists():
        error(f"Website file not found: {WEBSITE_FILE.name}")
        return False

    webbrowser.open(WEBSITE_FILE.resolve().as_uri())
    info(f"Opened {WEBSITE_FILE.name} in the browser.")
    return True


def generate_and_open_website() -> None:
    """Generate the HTML website and open it afterwards."""
    if generate_website():
        open_generated_website()


def _browser_app_is_available() -> bool:
    """Return True when the HTML frontend can be started from this checkout."""
    required_files = [
        TEMPLATE_FILE,
        HTML_DIR / "style.css",
        HTML_DIR / "movie_app.js",
    ]
    return all(file_path.exists() for file_path in required_files)


def _start_browser_app() -> bool:
    """Start the local HTTP server that serves the HTML frontend."""
    try:
        import movie_web_server
    except ModuleNotFoundError:
        error("Browser server not found. Falling back to CLI.")
        return False

    try:
        movie_web_server.main()
        return True
    except Exception as exc:
        error(f"Could not start browser app: {exc}")
        return False


def leave_program():
    print("Bye!")
    sys.exit(0)


# ---------------------------------------------------------
# MAIN MENU
# ---------------------------------------------------------


def print_main_menu():
    menu_options = {
        0: "Exit",
        1: "List movies",
        2: "Add movie",
        3: "Delete movie",
        4: "Update movie",
        5: "Stats",
        6: "Random movie",
        7: "Search movie",
        8: "Movies sorted by rating",
        9: "Movies sorted by year",
        10: "Create Rating Histogram",
        11: "Filter movies",
        12: "Switch user",
        13: "Generate HTML website",
    }

    print(f"{Colors.CYAN}\nMenu:{Colors.END}")
    for key, value in menu_options.items():
        print(f"{Colors.CYAN}{key}. {value}{Colors.END}")


def handle_choice(choice: int):
    actions = {
        0: leave_program,
        1: movie_list,
        2: add_movie,
        3: delete_movie,
        4: update_movie,
        5: stats_movies,
        6: random_movie,
        7: search_movie,
        8: movies_sorted_by_rating,
        9: movies_sorted_by_year,
        10: create_rating_histogram,
        11: filter_movies,
        12: switch_user,
        13: generate_and_open_website,
    }

    action = actions.get(choice)
    if action:
        action()
    else:
        error("Invalid choice")


def run_cli():
    print(f"{Colors.HEADER}********** My Movies Database **********{Colors.END}")
    print(f"{Colors.CYAN}Welcome to the Movie App! 🎬{Colors.END}")

    select_user()
    user_id, user_name = _get_active_user()
    sync_missing_movie_data(user_id)

    while True:
        print(f"{Colors.GREEN}Signed in as: {user_name}{Colors.END}")
        print_main_menu()

        try:
            choice = int(user_input("\nEnter choice (0-13): "))
            handle_choice(choice)
            user_id, user_name = _get_active_user()
        except ValueError:
            error("Please enter a number.")

        user_input("\nPress enter to continue")


def main():
    if _browser_app_is_available() and _start_browser_app():
        return

    run_cli()


if __name__ == "__main__":
    main()
