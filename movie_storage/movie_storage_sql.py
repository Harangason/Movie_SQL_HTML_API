"""
Movie storage module using SQLite with SQLAlchemy.

The public functions mirror the old JSON storage module so the rest of the
application can keep using get_movies(), add_movie(), delete_movie(), and
update_movie().
"""

import json
from pathlib import Path
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

BASE_DIR = Path(__file__).resolve().parent
_DB_CANDIDATES = [
    BASE_DIR / "data" / "movies.db",
    BASE_DIR.parent / "data" / "movies.db",
    BASE_DIR / "movies.db",
    BASE_DIR.parent / "movies.db",
]

for candidate in _DB_CANDIDATES:
    if candidate.exists():
        DB_PATH = candidate
        break
else:
    DB_PATH = BASE_DIR.parent / "data" / "movies.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"
LEGACY_MOVIE_FILE = BASE_DIR / "data.json"
DB_ECHO = os.getenv("MOVIE_DB_ECHO", "0").lower() in {"1", "true", "yes", "on"}

engine = create_engine(DB_URL, echo=DB_ECHO)


def _create_users_table() -> None:
    """Create users table if it does not exist."""
    with engine.connect() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                my_favorite_movie INTEGER,
                UNIQUE(name, last_name),
                FOREIGN KEY(my_favorite_movie) REFERENCES movies(id) ON DELETE SET NULL
            )
        """))
        connection.commit()


def _migrate_users_table_if_needed() -> None:
    """Migrate existing user tables to the new columns and constraints."""
    with engine.connect() as connection:
        users_tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            ).fetchall()
        }
        if "users" not in users_tables:
            return

        columns = connection.execute(text("PRAGMA table_info(users)")).fetchall()
        column_names = {column[1] for column in columns}

        if "last_name" not in column_names:
            connection.execute(text("ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''"))
        if "my_favorite_movie" not in column_names:
            connection.execute(text("ALTER TABLE users ADD COLUMN my_favorite_movie INTEGER"))
        connection.commit()


def _create_movies_table() -> None:
    """Create the movies table if it does not exist."""
    with engine.connect() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                rating REAL NOT NULL,
                poster TEXT,
                note TEXT,
                imdb_id TEXT,
                UNIQUE(title, year)
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


def _ensure_note_column() -> None:
    """Add the note column to existing databases created before note support."""
    with engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(movies)")).fetchall()
        column_names = {column[1] for column in columns}

        if "note" not in column_names:
            connection.execute(text("ALTER TABLE movies ADD COLUMN note TEXT"))
            connection.commit()


def _ensure_imdb_id_column() -> None:
    """Add the imdb_id column to existing databases created before imdb id support."""
    with engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(movies)")).fetchall()
        column_names = {column[1] for column in columns}

        if "imdb_id" not in column_names:
            connection.execute(text("ALTER TABLE movies ADD COLUMN imdb_id TEXT"))
            connection.commit()


def _year_to_int(year) -> int:
    """Convert legacy date strings like '14.10.1994' to an integer year."""
    if isinstance(year, int):
        return year

    year_text = str(year).strip()
    if "." in year_text:
        year_text = year_text.split(".")[-1]

    return int(year_text)


def _migrate_movies_table_if_needed() -> None:
    """Migrate old movie table schema to a shared movie catalog."""
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='movies'")
            ).fetchall()
        }
        if "movies" not in tables:
            return

        columns = connection.execute(text("PRAGMA table_info(movies)")).fetchall()
        column_names = {column[1] for column in columns}

        if "user_id" not in column_names:
            return

        connection.execute(text("ALTER TABLE movies RENAME TO movies_old"))
        connection.execute(text("""
            CREATE TABLE movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                rating REAL NOT NULL,
                poster TEXT,
                note TEXT,
                imdb_id TEXT,
                UNIQUE(title, year)
            )
        """))

        connection.execute(
            text("""
                INSERT OR IGNORE INTO movies (title, year, rating, poster, note, imdb_id)
                SELECT title, year, rating, poster, note
                  , NULL
                FROM movies_old
            WHERE id = (
                SELECT MIN(id)
                FROM movies_old AS source
                WHERE source.title = movies_old.title
                  AND source.year = movies_old.year
            )
            """),
        )
        connection.execute(text("DROP TABLE movies_old"))
        connection.commit()


def _create_default_user_if_empty() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        if result == 0:
            connection.execute(
                text("INSERT INTO users (name, last_name) VALUES ('Default', 'User')")
            )
            connection.commit()


def _get_user_by_name(name: str) -> int | None:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id FROM users WHERE name = :name"),
            {"name": name},
        ).fetchone()
        return row[0] if row else None


def get_users() -> dict[int, dict[str, str | None]]:
    """Return all users as a dictionary of user metadata."""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, name, last_name, my_favorite_movie
                FROM users
                ORDER BY name, last_name
                """
            )
        ).fetchall()

    return {
        row[0]: {
            "name": row[1],
            "last_name": row[2],
            "my_favorite_movie": row[3],
        }
        for row in rows
    }


def _normalize_last_name(last_name: str) -> str:
    return last_name.strip()


def get_user_id_or_create(name: str, last_name: str = "") -> int:
    """Return existing user id or create a new user."""
    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("User name cannot be empty.")
    trimmed_last_name = _normalize_last_name(last_name)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id FROM users
                WHERE name = :name AND last_name = :last_name
                """
            ),
            {"name": trimmed_name, "last_name": trimmed_last_name},
        ).fetchone()
        if row:
            return row[0]

        try:
            connection.execute(
                text("INSERT INTO users (name, last_name) VALUES (:name, :last_name)"),
                {"name": trimmed_name, "last_name": trimmed_last_name},
            )
        except IntegrityError:
            return connection.execute(
                text(
                    """
                    SELECT id FROM users
                    WHERE name = :name AND last_name = :last_name
                    """
                ),
                {"name": trimmed_name, "last_name": trimmed_last_name},
            ).scalar_one()

        connection.commit()
        return connection.execute(
            text(
                """
                SELECT id FROM users
                WHERE name = :name AND last_name = :last_name
                """
            ),
            {"name": trimmed_name, "last_name": trimmed_last_name},
        ).scalar_one()


def set_user_favorite_movie(user_id: int, movie_id: int | None) -> bool:
    """Set or clear a user's favorite movie reference."""
    with engine.connect() as connection:
        if movie_id is not None:
            exists = connection.execute(
                text("SELECT 1 FROM movies WHERE id = :movie_id"),
                {"movie_id": movie_id},
            ).scalar_one_or_none()
            if not exists:
                return False

        connection.execute(
            text(
                """
                UPDATE users
                SET my_favorite_movie = :movie_id
                WHERE id = :user_id
                """
            ),
            {"movie_id": movie_id, "user_id": user_id},
        )
        connection.commit()
        return True


def get_user_favorite_movie(user_id: int) -> int | None:
    """Return the favorite movie id for a user."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT my_favorite_movie FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).scalar_one_or_none()


def _migrate_legacy_json_if_database_is_empty() -> None:
    """Copy existing JSON movies into SQLite once, if the database is empty."""
    if not LEGACY_MOVIE_FILE.exists():
        return

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM movies")
        ).scalar_one()
        if count:
            return

        with open(LEGACY_MOVIE_FILE, "r", encoding="utf-8") as file:
            movies = json.load(file)

        for title, data in movies.items():
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO movies (title, year, rating, poster, note, imdb_id)
                    VALUES (:title, :year, :rating, :poster, NULL, :imdb_id)
                """),
                {
                    "title": title,
                    "year": _year_to_int(data["year"]),
                    "rating": float(data["rating"]),
                    "poster": data.get("poster"),
                    "imdb_id": data.get("imdb_id"),
                },
            )

        connection.commit()


def _initialize_database() -> None:
    _create_users_table()
    _migrate_users_table_if_needed()
    _create_movies_table()
    _ensure_poster_column()
    _ensure_note_column()
    _ensure_imdb_id_column()
    _migrate_movies_table_if_needed()
    _create_default_user_if_empty()
    _migrate_legacy_json_if_database_is_empty()


def list_movies(user_id: int) -> dict[str, dict]:
    """Retrieve all movies from the database."""
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT title, year, rating, poster, note, imdb_id FROM movies"),
        )
        movies = result.fetchall()

    return {
        row[0]: {
            "year": row[1],
            "rating": row[2],
            "poster": row[3],
            "note": row[4],
            "imdb_id": row[5],
        }
        for row in movies
    }


def get_movies(user_id: int) -> dict[str, dict]:
    """Return all movies using the same name as the old JSON storage module."""
    return list_movies(user_id)


def add_movie(
    title: str,
    year: int,
    rating: float,
    user_id: int,
    poster: str | None = None,
    note: str | None = None,
    imdb_id: str | None = None,
) -> bool:
    """Add a new movie to the database."""
    with engine.connect() as connection:
        try:
            connection.execute(
                text("""
                    INSERT INTO movies (title, year, rating, poster, note, imdb_id)
                    VALUES (:title, :year, :rating, :poster, :note, :imdb_id)
                """),
                {
                    "title": title,
                    "year": _year_to_int(year),
                    "rating": float(rating),
                    "poster": poster,
                    "note": note,
                    "imdb_id": imdb_id,
                },
            )
            connection.commit()
            print(f"Movie '{title}' added successfully.")
            return True
        except Exception as error:
            print(f"Error: {error}")
            return False


def delete_movie(title: str, user_id: int) -> bool:
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
    note: str | None = None,
    imdb_id: str | None = None,
    user_id: int | None = None,
) -> bool:
    """Update a movie's rating, year, poster URL, and note."""
    fields_to_update = {}

    if rating is not None:
        fields_to_update["rating"] = float(rating)

    if year is not None:
        fields_to_update["year"] = _year_to_int(year)

    if poster is not None:
        fields_to_update["poster"] = poster
    if note is not None:
        fields_to_update["note"] = note
    if imdb_id is not None:
        fields_to_update["imdb_id"] = imdb_id

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


def get_user_name(user_id: int) -> str | None:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()

    return row[0] if row else None


_initialize_database()
