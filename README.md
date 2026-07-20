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