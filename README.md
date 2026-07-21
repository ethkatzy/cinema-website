# cinema-website
[![CI](https://github.com/ethkatzy/cinema-website/actions/workflows/ci.yml/badge.svg)](https://github.com/ethkatzy/cinema-website/actions/workflows/ci.yml)
## Description
* On the website, users can search for upcoming films that are playing. The film page will incluce a poster, the film rating, a synopsis, the runtime, cast and crew and genre, as well as the times the film is playing.
* The user can create an account and log in to the website.
* The user can create, edit and delete bookings.
* The user can see films that have been added to the website.
* The user can search for films by their title, as well as keywords based on other information on the film page.
* The user page shows all past and future bookings the user has.
* The user can select one or more classifications for the film.
* The user can make a booking for a film, including the number of seats, and picking which seat they want to sit in.
* An admin account can add new films, screens, and showings from `/admin` without editing `schema.sql` by hand.

## How to run
Clone the repository, and install the dependencies from the repo root:
```
pip install -r requirements.txt
```

### Re-installing the database:
If you wish to create a new database from the schema, you can run the following command `sqlite CinemaDatabase.db < schema.sql`.

### Launching the website:
Do one of the following:
* Run `main.py` from an IDE
* Run the command `flask run`
* Execute `main.py` from the command line

Then in a browser open `127.0.0.1:5000`.

### Admin access
`schema.sql` seeds one demo admin account:
* Email: `admin@cinema.local`
* Password: `AdminDemo123!`

Log in with those credentials and an "Admin" link appears in the nav bar, linking to `/admin` — forms for adding films, screens, and showings. This is a demo credential for coursework purposes only; rotate or remove it before any real deployment.

### Running tests
Install the test dependency and run pytest from the repo root:
```
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
Tests run against a temporary SQLite database built from `schema.sql`, so they never touch `CinemaDatabase.db`.

### Linting
```
ruff check .
```

### CI
Every push and pull request against `main` runs lint (`ruff`) and the test suite (`pytest`) via GitHub Actions — see `.github/workflows/ci.yml`.

### Deploying (Render)
The repo includes a `render.yaml` blueprint, so Render can build and run the app with no manual config:
1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. On [render.com](https://render.com), New → Blueprint → connect the `cinema-website` repo. Render reads `render.yaml` and creates a free web service (`gunicorn` serving `main:app`).
3. Render sets `FLASK_ENV=production` and generates a random `CINEMA_SECRET_KEY` automatically (see `render.yaml`).
4. On first boot, `main.py` creates `CinemaDatabase.db` from `schema.sql` if it doesn't already exist (the `.db` file itself is gitignored, so it's never committed).

Note: Render's free tier disk is ephemeral, so `CinemaDatabase.db` — and anything written to it (signups, bookings) — resets to the `schema.sql` seed data on every redeploy. That's fine for a demo/portfolio link; it isn't a durable production database.

## Known limitations
* Runs via Flask's dev server for this demo; a production deployment would put gunicorn behind nginx.
* SQLite serializes writes (only one writer at a time), so it has a hard concurrency ceiling and isn't suited to high-concurrency production traffic. WAL mode (`PRAGMA journal_mode=WAL`, set in `get_db()`) lets readers proceed alongside a writer, but it doesn't remove the single-writer limit.