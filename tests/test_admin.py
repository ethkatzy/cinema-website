import datetime as dt
import sqlite3

from conftest import login_session

ADMIN_ROUTES = ["/admin", "/admin/films/new", "/admin/screens/new", "/admin/showings/new"]


def test_anonymous_gets_login_page_on_admin_routes(client):
    for route in ADMIN_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 200
        assert b'name="password"' in resp.data


def test_non_admin_user_is_forbidden(client, make_user):
    user = make_user(email="regular@example.com", is_admin=False)
    login_session(client, user["email"])
    for route in ADMIN_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 403


def test_admin_can_reach_dashboard(client, make_user):
    admin = make_user(email="admin1@example.com", is_admin=True)
    login_session(client, admin["email"], is_admin=True)
    resp = client.get("/admin")
    assert resp.status_code == 200


def test_admin_can_create_film(client, db_path, make_user):
    admin = make_user(email="admin2@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    resp = client.post("/admin/films/new", data={
        "title": "Test Film",
        "description": "A film for testing",
        "duration": "100",
        "releasedate": "1st Jan 2026",
        "rating": "PG",
        "posterurl": "https://example.com/poster.jpg",
        "actors": "Someone",
        "director": "Someone Else",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT title, duration, rating FROM film WHERE title = ?", ("Test Film",)).fetchone()
    conn.close()
    assert row == ("Test Film", 100.0, "PG")


def test_film_creation_rejects_unknown_rating(client, db_path, make_user):
    admin = make_user(email="admin3@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    resp = client.post("/admin/films/new", data={
        "title": "Bad Rating Film",
        "description": "",
        "duration": "100",
        "releasedate": "",
        "rating": "NC-17",
        "posterurl": "",
        "actors": "",
        "director": "",
        "csrf_token": token,
    })
    assert resp.status_code == 200
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM film WHERE title = ?", ("Bad Rating Film",)).fetchone()[0]
    conn.close()
    assert count == 0


def test_admin_can_create_screen_with_seats(client, db_path, make_user):
    admin = make_user(email="admin4@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    resp = client.post("/admin/screens/new", data={"screenname": "Screen 12", "csrf_token": token})
    assert resp.status_code == 302
    conn = sqlite3.connect(db_path)
    screen_id = conn.execute("SELECT screenid FROM screen WHERE screenname = ?", ("Screen 12",)).fetchone()[0]
    seat_count = conn.execute("SELECT COUNT(*) FROM seat WHERE screenid = ?", (screen_id,)).fetchone()[0]
    conn.close()
    assert seat_count == 150


def _create_film(client, token, title):
    resp = client.post("/admin/films/new", data={
        "title": title,
        "description": "",
        "duration": "100",
        "releasedate": "",
        "rating": "PG",
        "posterurl": "",
        "actors": "",
        "director": "",
        "csrf_token": token,
    })
    assert resp.status_code == 302


def test_admin_can_create_showing(client, db_path, make_user):
    admin = make_user(email="admin5@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    _create_film(client, token, "Showing Test Film 1")
    conn = sqlite3.connect(db_path)
    film_id = conn.execute("SELECT filmid FROM film WHERE title = ?", ("Showing Test Film 1",)).fetchone()[0]
    conn.close()

    date_str = (dt.date.today() + dt.timedelta(days=2)).isoformat()
    resp = client.post("/admin/showings/new", data={
        "film_id": str(film_id),
        "screen_id": "10",
        "start_date": date_str,
        "time": "10:00",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        """SELECT COUNT(*) FROM showingtemplate
        WHERE filmid = ? AND screenid = 10 AND showtime = '10:00' AND start_date = ? AND end_date = ?""",
        (film_id, date_str, date_str),
    ).fetchone()[0]
    conn.close()
    assert count == 1

    # The new showing must actually be discoverable, not just materialize on
    # the exact showing URL — that's what broke before this test existed.
    film_resp = client.get("/film/showing-test-film-1")
    assert date_str.encode() in film_resp.data


def test_showing_creation_rejects_screen_overlap(client, db_path, make_user):
    admin = make_user(email="admin6@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    _create_film(client, token, "Showing Test Film 2")
    conn = sqlite3.connect(db_path)
    film_id = conn.execute("SELECT filmid FROM film WHERE title = ?", ("Showing Test Film 2",)).fetchone()[0]
    conn.close()
    date_str = (dt.date.today() + dt.timedelta(days=2)).isoformat()

    first = client.post("/admin/showings/new", data={
        "film_id": str(film_id), "screen_id": "10", "start_date": date_str, "time": "12:00", "csrf_token": token,
    })
    assert first.status_code == 302

    second = client.post("/admin/showings/new", data={
        "film_id": str(film_id), "screen_id": "10", "start_date": date_str, "time": "13:00", "csrf_token": token,
    })
    assert second.status_code == 200
    assert b"overlap" in second.data.lower()

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM showingtemplate WHERE filmid = ? AND screenid = 10", (film_id,)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_showing_creation_enforces_per_day_per_film_cap(client, db_path, make_user):
    admin = make_user(email="admin7@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    date_str = (dt.date.today() + dt.timedelta(days=2)).isoformat()

    # Film 1's seeded templates already produce 4 showings/day on screen 1,
    # so a 5th (even on a different screen) should be rejected by the cap.
    resp = client.post("/admin/showings/new", data={
        "film_id": "1", "screen_id": "10", "start_date": date_str, "time": "10:00", "csrf_token": token,
    })
    assert resp.status_code == 200
    assert b"showings on" in resp.data.lower() or b"already has" in resp.data.lower()

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM showingtemplate WHERE screenid = 10"
    ).fetchone()[0]
    conn.close()
    assert count == 0


def test_showing_creation_supports_recurring_range(client, db_path, make_user):
    admin = make_user(email="admin8@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    _create_film(client, token, "Recurring Test Film")
    conn = sqlite3.connect(db_path)
    film_id = conn.execute("SELECT filmid FROM film WHERE title = ?", ("Recurring Test Film",)).fetchone()[0]
    conn.close()

    start_date = dt.date.today() + dt.timedelta(days=2)
    end_date = start_date + dt.timedelta(days=13)  # every day for two weeks

    resp = client.post("/admin/showings/new", data={
        "film_id": str(film_id),
        "screen_id": "10",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "weekdays": ["1", "2", "3", "4", "5", "6", "7"],
        "time": "10:00",
        "csrf_token": token,
    })
    assert resp.status_code == 302

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """SELECT weekdays, start_date, end_date FROM showingtemplate
        WHERE filmid = ? AND screenid = 10""", (film_id,)
    ).fetchone()
    conn.close()
    assert row == ("1,2,3,4,5,6,7", start_date.isoformat(), end_date.isoformat())

    slug = "recurring-test-film"
    film_resp = client.get(f"/film/{slug}")
    assert start_date.isoformat().encode() in film_resp.data
    assert (start_date + dt.timedelta(days=7)).isoformat().encode() in film_resp.data


def test_showing_creation_rejects_range_over_max_days(client, db_path, make_user):
    admin = make_user(email="admin9@example.com", is_admin=True)
    token = login_session(client, admin["email"], is_admin=True)
    _create_film(client, token, "Too Long Range Film")
    conn = sqlite3.connect(db_path)
    film_id = conn.execute("SELECT filmid FROM film WHERE title = ?", ("Too Long Range Film",)).fetchone()[0]
    conn.close()

    start_date = dt.date.today() + dt.timedelta(days=2)
    end_date = start_date + dt.timedelta(days=200)

    resp = client.post("/admin/showings/new", data={
        "film_id": str(film_id),
        "screen_id": "10",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "weekdays": ["1"],
        "time": "10:00",
        "csrf_token": token,
    })
    assert resp.status_code == 200
    assert b"90-day" in resp.data

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM showingtemplate WHERE filmid = ?", (film_id,)
    ).fetchone()[0]
    conn.close()
    assert count == 0
