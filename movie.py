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
Designed for simplicity and user-friendliness with colored terminal output.
"""

from html import escape
from pathlib import Path
import random
import sys
from datetime import datetime
from difflib import get_close_matches

try:
    from fuzzywuzzy import process
except ModuleNotFoundError:
    process = None

import movie_storage_sql as movie_storage
import omdb_api

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR / "index_template.html"
WEBSITE_FILE = BASE_DIR / "index.html"
APP_TITLE = "My Movie App"


# ---------------------------------------------------------
# UI + COLORS
# ---------------------------------------------------------

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


def format_poster(poster: str | None) -> str:
    """Return display text for a poster URL value."""
    if not poster or poster == "N/A":
        return "No poster available"

    return poster


def sync_missing_movie_data() -> None:
    """Automatically enrich old database entries with OMDb data."""
    movies = movie_storage.get_movies()
    movies_without_poster = [
        title
        for title, data in movies.items()
        if not data.get("poster")
    ]

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
        ):
            updated_count += 1

    if updated_count:
        info(f"Updated {updated_count} old movie record(s) with OMDb data.")

    if failed_titles:
        info(f"Could not update {len(failed_titles)} old movie record(s) from OMDb.")


# ---------------------------------------------------------
# SEARCH + SELECT
# ---------------------------------------------------------

def suggest_similar_movies(movie_name: str, movies: dict) -> list[str]:
    """Returns top 3 fuzzy suggestions."""
    titles = list(movies.keys())

    if process is None:
        return get_close_matches(movie_name, titles, n=3, cutoff=0.6)

    suggestions = process.extract(movie_name, titles, limit=3)
    return [title for title, score in suggestions if score > 60]


def select_movie_name(movies: dict, prompt: str = "Enter movie name: ") -> str | None:
    """Central search function handling exact, partial, and fuzzy matching."""
    user_input_name = user_input(prompt).strip()

    if not user_input_name:
        error("Movie name cannot be empty")
        return None

    name_lower = user_input_name.lower()

    # 1) Exact match
    if user_input_name in movies:
        return user_input_name

    # 2) Partial match
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

    # 3) Fuzzy match
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


# ---------------------------------------------------------
# MOVIE FUNCTIONS
# ---------------------------------------------------------

def movie_list():
    """Prints all movies."""
    movies = movie_storage.get_movies()
    info(f"\n{len(movies)} movies in total")

    for title, data in movies.items():
        year = data.get("year", "unknown")
        rating = data.get("rating", 0)
        poster = format_poster(data.get("poster"))
        info(f"{title} ({year}): {rating}")
        info(f"Poster: {poster}")


def add_movie():
    """Adds a new movie with title, year, rating, and poster URL from OMDb."""
    movies = movie_storage.get_movies()
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
        movie_data["poster"],
    ):
        info(f"Movie '{title}' added from OMDb.")
        info(f"Year: {movie_data['year']}")
        info(f"Rating: {movie_data['rating']}")
        info(f"Poster: {format_poster(movie_data['poster'])}")


def delete_movie():
    """Deletes a movie."""
    movies = movie_storage.get_movies()
    movie_name = select_movie_name(movies, "Enter movie name to delete: ")

    if movie_name and movie_storage.delete_movie(movie_name):
        info(f"Movie '{movie_name}' deleted.")
    else:
        error("Movie not found.")


def update_movie(movie_name: str = None):
    """Updates a movie's rating."""
    movies = movie_storage.get_movies()

    if movie_name is None:
        movie_name = select_movie_name(movies, "Enter movie name to update: ")

    if movie_name not in movies:
        error("Movie not found.")
        return

    rating_input = user_input("Enter new rating (or press Enter to cancel): ").strip()

    if not rating_input:
        info("Update cancelled.")
        return

    try:
        new_rating = float(rating_input.replace(",", "."))
    except ValueError:
        error("Invalid rating")
        return

    if movie_storage.update_movie(movie_name, new_rating):
        info(f"Movie '{movie_name}' updated.")
    else:
        error("Update failed.")


def search_movie():
    """Searches for a movie."""
    movies = movie_storage.get_movies()
    movie_name = select_movie_name(movies, "Enter part of movie name: ")

    if movie_name and movie_name in movies:
        data = movies[movie_name]
        poster = format_poster(data.get("poster"))
        info(f"{movie_name}: Rating: {data.get('rating')}, Year: {data.get('year')}")
        info(f"Poster: {poster}")
    else:
        error("Movie not found.")


# ---------------------------------------------------------
# STATS
# ---------------------------------------------------------

def stats_movies():
    """Shows statistics."""
    movies = movie_storage.get_movies()

    if not movies:
        error("No movies available.")
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
    movies = movie_storage.get_movies()

    if not movies:
        error("No movies available.")
        return

    movie = random.choice(list(movies.keys()))
    info(f"\nYour movie for tonight: {movie}, rated {movies[movie]['rating']}")


def movies_sorted_by_rating():
    """Lists movies sorted by rating (descending)."""
    movies = movie_storage.get_movies()
    sorted_list = sorted(movies.items(), key=lambda item: item[1]["rating"], reverse=True)

    for title, data in sorted_list:
        info(f"{title}: {data['rating']}")

def movies_sorted_by_year():
    """Lists movies sorted by year (descending)."""
    movies = movie_storage.get_movies()

    sorted_list = sorted(
        movies.items(),
        key=lambda item: int(item[1]["year"]),
        reverse=True
    )

    for title, data in sorted_list:
        info(f"{title}: {data['year']}")

def add_timestamps_to_movies(movies):
    """Fügt jedem Film im Dictionary einen Unix-Timestamp hinzu."""
    for title, data in movies.items():
        # 1. Convert a string to a datetime object
        date_obj = datetime(int(data["year"]), 1, 1)

        # 2. Generate a timestamp (as an integer)
        timestamp = int(date_obj.timestamp())

        # 3. Save the new value in the dictionary
        data["timestamp"] = timestamp

    return movies

def filter_movies():
    """Filters movies based on min rating and a year range."""
    movies = movie_storage.get_movies()

    # 1. user input
    min_rate_input = user_input("Enter minimum rating (leave blank for no minimum rating): ").strip()
    start_year_input = user_input("Enter start year (leave blank for no start year): ").strip()
    end_year_input = user_input("Enter end year (leave blank for no end year): ").strip()

    filtered_movies = {}

    # 2. check all movies by rate
    for title, data in movies.items():
        # Check rating filters
        if min_rate_input:
            if data["rating"] < float(min_rate_input):
                continue  #  Skip the film if the rating is too low

        movie_year = int(data["year"])

        if start_year_input:
            if movie_year < int(start_year_input):
                continue  # Skip the film if the year of release is

        if end_year_input:
            if movie_year > int(end_year_input):
                continue  # Skip the film if, after the end year

        # If all filters have been passed, add to the results
        filtered_movies[title] = data

    # 3. Display the result
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

    movies = movie_storage.get_movies()
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
    movie_items = []

    for title, data in movies.items():
        safe_title = escape(title)
        safe_year = escape(str(data.get("year", "unknown")))
        poster = data.get("poster")
        poster_html = '<div class="movie-poster"></div>'

        if poster and poster != "N/A":
            safe_poster = escape(poster, quote=True)
            poster_html = (
                f'<img class="movie-poster" src="{safe_poster}" '
                f'alt="{safe_title} poster"/>'
            )

        movie_items.append(
            "            <li>\n"
            '                <div class="movie">\n'
            f"                    {poster_html}\n"
            f'                    <div class="movie-title">{safe_title}</div>\n'
            f'                    <div class="movie-year">{safe_year}</div>\n'
            "                </div>\n"
            "            </li>"
        )

    return "\n".join(movie_items)


def generate_website():
    """Generate index.html from the movie database and HTML template."""
    if not TEMPLATE_FILE.exists():
        error(f"Template file not found: {TEMPLATE_FILE.name}")
        return

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    movies = movie_storage.get_movies()
    movie_grid = generate_movie_grid(movies)

    website_html = template.replace("__TEMPLATE_TITLE__", escape(APP_TITLE))
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
        12: "Generate website",
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
        12: generate_website,
    }

    action = actions.get(choice)
    if action:
        action()
    else:
        error("Invalid choice")


def main():
    print(f"{Colors.HEADER}********** My Movies Database **********{Colors.END}")
    sync_missing_movie_data()

    while True:
        print_main_menu()

        try:
            choice = int(user_input("\nEnter choice (0-12): "))
            handle_choice(choice)
        except ValueError:
            error("Please enter a number.")

        user_input("\nPress enter to continue")


if __name__ == "__main__":
    main()
