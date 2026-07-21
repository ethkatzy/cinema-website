import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("FLASK_ENV", "development")

import main  # noqa: E402

SCHEMA_SQL = (ROOT_DIR / "schema.sql").read_text(encoding="utf-8", errors="replace")


@pytest.fixture(autouse=True)
def reset_rate_limits():
    main._login_attempts.clear()
    yield
    main._login_attempts.clear()


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setattr(main, "DB_PATH", str(path))
    return str(path)


@pytest.fixture()
def app(db_path):
    main.app.config.update(TESTING=True)
    yield main.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(db_path):
    def _make(email="user@example.com", password="Password123!",
              username="Test User", phone="07000000000"):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO user (username, email, phonenumber, passwordhash) VALUES (?, ?, ?, ?)",
            (username, email, phone, generate_password_hash(password)),
        )
        conn.commit()
        userid = conn.execute("SELECT userid FROM user WHERE email = ?", (email,)).fetchone()[0]
        conn.close()
        return {"userid": userid, "email": email, "password": password, "username": username}

    return _make


def login_session(client, email, csrf_token="test-csrf-token"):
    """Log a test client in directly via the session, bypassing the real login form."""
    with client.session_transaction() as sess:
        sess["email"] = email
        sess["csrf_token"] = csrf_token
    return csrf_token


def csrf_token_from_get(client, path):
    """Perform a real GET request and read back the CSRF token the route issued."""
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


@pytest.fixture()
def seeded_showing(db_path):
    """Two showing rows dated 'tomorrow' relative to whenever the suite runs,
    on screens 10 and 11 (no showingtemplate targets those screens), so tests
    can drive bookings through the real HTTP routes regardless of the date."""
    showing_date = (dt.datetime.now() + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO showing (filmid, screenid, datetime) VALUES (1, 10, ?)",
                 (f"{showing_date} 14:05",))
    conn.execute("INSERT INTO showing (filmid, screenid, datetime) VALUES (1, 11, ?)",
                 (f"{showing_date} 14:50",))
    conn.commit()
    showing_id = conn.execute(
        "SELECT showingid FROM showing WHERE screenid = 10 AND datetime = ?", (f"{showing_date} 14:05",)
    ).fetchone()[0]
    other_screen_showing_id = conn.execute(
        "SELECT showingid FROM showing WHERE screenid = 11 AND datetime = ?", (f"{showing_date} 14:50",)
    ).fetchone()[0]
    conn.close()
    return {
        "showing_id": showing_id,
        "other_screen_showing_id": other_screen_showing_id,
        "url": f"/showing/{showing_date}/14:05/screen-10",
    }


def get_seat_ids(db_path, showing_id, limit=2):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    seats = main.get_seats_for_showing(cursor, showing_id)
    conn.close()
    return [seat["seatid"] for seat in seats[:limit]]


def create_booking_directly(db_path, userid, showingid, seatid, otherinfo=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO booking (userid, showingid, bookingtime, totalprice, otherinfo)
        VALUES (?, ?, datetime('now'), ?, ?)""",
        (userid, showingid, main.TICKET_PRICE, otherinfo),
    )
    bookingid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO bookingdetail (bookingid, showingid, seatid) VALUES (?, ?, ?)",
                 (bookingid, showingid, seatid))
    conn.commit()
    conn.close()
    return bookingid
