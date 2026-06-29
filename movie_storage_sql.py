"""
Movie storage module using SQLite with SQLAlchemy.

The public functions mirror the old JSON storage module so the rest of the
application can keep using get_movies(), add_movie(), delete_movie(), and
update_movie().
"""

import json
from pathlib import Path

from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "movies.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"
LEGACY_MOVIE_FILE = BASE_DIR / "data.json"

engine = create_engine(DB_URL, echo=True)


def _create_movies_table() -> None:
    """Create the movies table if it does not exist."""
    with engine.connect() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE NOT NULL,
                year INTEGER NOT NULL,
                rating REAL NOT NULL,
                poster TEXT
            )
        """))
        connection.commit()


def _ensure_poster_column() -> None:
    """Add the poster column to existing databases created before poster support."""
    with engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(movies)")).fetchall()
        column_names = {column[1] for column in columns}

        if "poster" not in column_names:
            connection.execute(text("ALTER TABLE movies ADD COLUMN poster TEXT"))
            connection.commit()


def _year_to_int(year) -> int:
    """Convert legacy date strings like '14.10.1994' to an integer year."""
    if isinstance(year, int):
        return year

    year_text = str(year).strip()
    if "." in year_text:
        year_text = year_text.split(".")[-1]

    return int(year_text)


def _migrate_legacy_json_if_database_is_empty() -> None:
    """Copy existing JSON movies into SQLite once, if the database is empty."""
    if not LEGACY_MOVIE_FILE.exists():
        return

    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM movies")).scalar_one()
        if count:
            return

        with open(LEGACY_MOVIE_FILE, "r", encoding="utf-8") as file:
            movies = json.load(file)

        for title, data in movies.items():
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO movies (title, year, rating, poster)
                    VALUES (:title, :year, :rating, :poster)
                """),
                {
                    "title": title,
                    "year": _year_to_int(data["year"]),
                    "rating": float(data["rating"]),
                    "poster": data.get("poster"),
                },
            )

        connection.commit()


def _initialize_database() -> None:
    _create_movies_table()
    _ensure_poster_column()
    _migrate_legacy_json_if_database_is_empty()


def list_movies() -> dict[str, dict]:
    """Retrieve all movies from the database."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT title, year, rating, poster FROM movies"))
        movies = result.fetchall()

    return {
        row[0]: {
            "year": row[1],
            "rating": row[2],
            "poster": row[3],
        }
        for row in movies
    }


def get_movies() -> dict[str, dict]:
    """Return all movies using the same name as the old JSON storage module."""
    return list_movies()


def add_movie(title: str, year: int, rating: float, poster: str | None = None) -> bool:
    """Add a new movie to the database."""
    with engine.connect() as connection:
        try:
            connection.execute(
                text("""
                    INSERT INTO movies (title, year, rating, poster)
                    VALUES (:title, :year, :rating, :poster)
                """),
                {
                    "title": title,
                    "year": _year_to_int(year),
                    "rating": float(rating),
                    "poster": poster,
                },
            )
            connection.commit()
            print(f"Movie '{title}' added successfully.")
            return True
        except Exception as error:
            print(f"Error: {error}")
            return False


def delete_movie(title: str) -> bool:
    """Delete a movie from the database."""
    with engine.connect() as connection:
        result = connection.execute(
            text("DELETE FROM movies WHERE title = :title"),
            {"title": title},
        )
        connection.commit()

    if result.rowcount > 0:
        print(f"Movie '{title}' deleted successfully.")
        return True

    print(f"Movie '{title}' not found.")
    return False


def update_movie(
    title: str,
    rating: float | None = None,
    year: int | None = None,
    poster: str | None = None,
) -> bool:
    """Update a movie's rating, year, and/or poster URL in the database."""
    fields_to_update = {}

    if rating is not None:
        fields_to_update["rating"] = float(rating)

    if year is not None:
        fields_to_update["year"] = _year_to_int(year)

    if poster is not None:
        fields_to_update["poster"] = poster

    if not fields_to_update:
        print(f"No update data provided for '{title}'.")
        return False

    set_clause = ", ".join(f"{field} = :{field}" for field in fields_to_update)
    values = {
        **fields_to_update,
        "title": title,
    }

    with engine.connect() as connection:
        result = connection.execute(
            text(f"UPDATE movies SET {set_clause} WHERE title = :title"),
            values,
        )
        connection.commit()

    if result.rowcount > 0:
        print(f"Movie '{title}' updated successfully.")
        return True

    print(f"Movie '{title}' not found.")
    return False


_initialize_database()
