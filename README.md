# Movie_SQL_HTML_API

A Python movie manager with two faces:

- a command-line interface for managing movies and users
- a generated HTML/JavaScript frontend that talks to a local HTTP API

The app stores data in SQLite, loads posters and metadata from OMDb, and renders the same movie catalogue in both CLI and browser form.

## Features

- list, add, update, and delete movies
- search, filter, sort, and show random movies
- show movie statistics and a rating histogram
- switch between users and create new users
- generate an HTML movie dashboard from the template in `HTML/index_template.html`
- serve the browser app through a local web server with static CSS and JS assets

## Project Layout

- `movie.py` - main application logic and HTML generation
- `movie_web_server.py` - local HTTP server for the browser app and API
- `omdb_api.py` - OMDb integration for movie metadata
- `Movie_SQL_HTML_API/movie_storage/` - SQLite-backed storage layer
- `Movie_SQL_HTML_API/HTML/` - template, generated page, CSS, and browser app
- `Movie_SQL_HTML_API/data/` - SQLite database file

## Run

### CLI version

```bash
python movie.py
```

### Browser version

```bash
python movie_web_server.py
```

Then open:

```text
http://127.0.0.1:5000/
```

## Notes

- The generated page is written to `Movie_SQL_HTML_API/HTML/movies.html`.
- If you open the HTML file directly, it works as a static page.
- For the full interactive experience, use the local HTTP server so the CSS, JavaScript, and API endpoints are available.
