# Cinema Website

[![CI](https://github.com/ethkatzy/cinema-website/actions/workflows/ci.yml/badge.svg)](https://github.com/ethkatzy/cinema-website/actions/workflows/ci.yml)

**Live demo: https://cinema-website-ztjt.onrender.com** (free Render tier — the first request after idle can take ~30s to wake up)

A mock cinema booking website built for a university Databases and Web Programming module. It's a full-stack Flask + SQLite app covering film listings, seat-accurate booking with live availability, account management, and an admin dashboard for managing films, screens (with a custom seat-layout designer), and recurring showings. The database is never hand-edited. It's meant to demonstrate relational schema design, server-side rendering, and the kind of security hygiene (CSRF, rate limiting, security headers, parameterised queries) that a real deployment would need.

## Tech stack

- **Backend:** Flask 3, Python, `sqlite3` (standard library — no ORM)
- **Frontend:** Server-rendered Jinja2 templates, vanilla CSS/JS (no frontend framework or build step)
- **Database:** SQLite, with WAL mode enabled for concurrent reads
- **Auth:** Session cookies + `werkzeug.security` password hashing (no third-party auth library)
- **Testing/Linting:** `pytest`, `ruff`
- **Deployment:** `gunicorn`, deployed to Render via `render.yaml`

## Setup / running locally

Clone the repo, then from the repo root:

```
pip install -r requirements.txt
```

Run the app with any of:

```
python main.py
# or
flask run
```

Then open `127.0.0.1:5000` in a browser. On first run, `main.py` automatically creates `CinemaDatabase.db` from `schema.sql` (seeded with 9 films, 11 screens, and their seat layouts) if the file doesn't already exist.

### Admin access

`schema.sql` seeds one demo admin account:

- Email: `admin@cinema.local`
- Password: `AdminDemo123!`

Logging in with those credentials adds an "Admin" link to the nav bar, linking to `/admin`, which contains forms for adding films, screens (via a 3-step seat-layout wizard), and showings. This is a demo credential for coursework purposes only.

### Rebuilding the database

To wipe local data and start again from the seed data:

```
sqlite3 CinemaDatabase.db < schema.sql
```

### Running tests

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

Every push and pull request against `main` runs `ruff check` and `pytest` via GitHub Actions (`.github/workflows/ci.yml`).

## Key features

- **Browse & search:** film listings with poster, age rating icon, synopsis, runtime, cast/crew, and showtimes; search by title and/or date.
- **Recurring showings:** admins define a showing once (film, screen, days of the week, start time, date range) as a `showingtemplate` row; the app expands that into concrete showing instances on the fly rather than pre-generating rows for every date.
- **Seat-accurate booking:** pick individual seats on a rendered seating grid, including irregular per-screen layouts (missing rows/gaps) and three seat tiers (Saver/Regular/VIP) with different prices, with already-booked seats disabled.
- **Booking management:** users can view, edit (change seats), or cancel any of their bookings from their account page.
- **Accounts:** signup with email/phone/password format validation and duplicate-email detection, login with rate limiting (5 attempts / 5 minutes per IP+email).
- **Admin dashboard (`/admin`):** add films, design a screen's seat layout through a 3-step wizard, and schedule showings, with overlap detection (no double-booking a screen) and a per-film daily showing cap, all enforced server-side.
- **Security hardening:** CSRF tokens on all state-changing forms, parameterised SQL throughout, security headers (CSP, X-Frame-Options, HSTS in production), `SESSION_COOKIE_SECURE`/`HttpOnly`/`SameSite`, and custom 400/403/404/409/410/429/500 error pages instead of Flask's defaults.

## Known limitations

This is a coursework/portfolio demo, not a production system. If it were going into real production:

- **Dev server vs WSGI:** local runs use Flask's built-in dev server; the deployed version already runs behind `gunicorn`, but a real deployment would put that behind a reverse proxy like `nginx` and probably add multiple workers/processes.
- **SQLite concurrency:** SQLite serializes writes (one writer at a time). WAL mode (enabled in `get_db()`) lets readers proceed alongside a writer, but doesn't remove the single-writer ceiling. This is fine for a demo, not for high-concurrency production traffic. A real system would likely move to Postgres.
- **Ephemeral storage on Render's free tier:** `CinemaDatabase.db` is gitignored and rebuilt from `schema.sql` on first boot if missing. Render's free tier disk isn't persistent, so any data written at runtime (signups, bookings) resets on redeploy.
- **No payment processing:** bookings compute a total price but there's no real payment integration.
- **No ORM/migrations:** schema changes are handwritten SQL (`schema.sql`) rather than versioned migrations, which is fine at this scale but wouldn't scale to a team or a schema that changes often.
