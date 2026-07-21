import sqlite3

from conftest import create_booking_directly, get_seat_ids, login_session


def test_showing_page_lists_seats(client, seeded_showing):
    resp = client.get(seeded_showing["url"])
    assert resp.status_code == 200
    assert b"Confirm Booking" in resp.data


def test_showing_page_404s_for_nonexistent_showing(client, seeded_showing):
    resp = client.get(seeded_showing["url"].replace("screen-10", "screen-999"))
    assert resp.status_code == 404


def test_showing_page_410s_for_past_showing(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO showing (filmid, screenid, datetime) VALUES (1, 10, '2020-01-01 14:05')")
    conn.commit()
    conn.close()

    resp = client.get("/showing/2020-01-01/14:05/screen-10")
    assert resp.status_code == 410


def test_booking_without_login_does_not_create_booking(client, db_path, seeded_showing):
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    resp = client.post(seeded_showing["url"], data={"seats": [str(seat_id)]})
    assert resp.status_code == 200
    assert b"Sign in" in resp.data
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM booking").fetchone()[0]
    conn.close()
    assert count == 0


def test_booking_with_no_seats_requires_csrf(client, seeded_showing):
    resp = client.post(seeded_showing["url"], data={})
    assert resp.status_code == 403


def test_booking_without_csrf_token_is_rejected(client, make_user, db_path, seeded_showing):
    user = make_user(email="nocsrf-book@example.com")
    login_session(client, user["email"])
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    resp = client.post(seeded_showing["url"], data={"seats": [str(seat_id)], "other-info": ""})
    assert resp.status_code == 403


def test_booking_creates_booking_for_logged_in_user(client, db_path, make_user, seeded_showing):
    user = make_user(email="booker@example.com")
    token = login_session(client, user["email"])
    seat_ids = get_seat_ids(db_path, seeded_showing["showing_id"], limit=2)

    resp = client.post(seeded_showing["url"], data={
        "seats": [str(s) for s in seat_ids],
        "other-info": "wheelchair access",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/account"

    conn = sqlite3.connect(db_path)
    booking = conn.execute(
        "SELECT bookingid, userid, totalprice, otherinfo FROM booking"
    ).fetchone()
    seats_booked = {
        row[0] for row in conn.execute(
            "SELECT seatid FROM bookingdetail WHERE bookingid = ?", (booking[0],)
        ).fetchall()
    }
    conn.close()

    assert booking[1] == user["userid"]
    assert booking[2] == 8.99 * 2
    assert booking[3] == "wheelchair access"
    assert seats_booked == set(seat_ids)


def test_booking_rejects_seat_already_booked_by_someone_else(client, db_path, make_user, seeded_showing):
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    first_user = make_user(email="first-booker@example.com")
    create_booking_directly(db_path, first_user["userid"], seeded_showing["showing_id"], seat_id)

    second_user = make_user(email="second-booker@example.com")
    token = login_session(client, second_user["email"])
    resp = client.post(seeded_showing["url"], data={
        "seats": [str(seat_id)], "other-info": "", "csrf_token": token,
    })
    assert resp.status_code == 409


def test_booking_rejects_seat_not_belonging_to_showings_screen(client, db_path, make_user, seeded_showing):
    seat_from_other_screen = get_seat_ids(db_path, seeded_showing["other_screen_showing_id"], limit=1)[0]
    user = make_user(email="wrongscreen@example.com")
    token = login_session(client, user["email"])
    resp = client.post(seeded_showing["url"], data={
        "seats": [str(seat_from_other_screen)], "other-info": "", "csrf_token": token,
    })
    assert resp.status_code == 409


def test_delete_booking_blocks_non_owner(client, db_path, make_user, seeded_showing):
    owner = make_user(email="owner@example.com")
    attacker = make_user(email="attacker@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)

    token = login_session(client, attacker["email"])
    resp = client.post("/delete", data={"booking_id": bookingid, "csrf_token": token})
    assert resp.status_code == 403

    conn = sqlite3.connect(db_path)
    still_exists = conn.execute(
        "SELECT 1 FROM booking WHERE bookingid = ?", (bookingid,)
    ).fetchone()
    conn.close()
    assert still_exists is not None


def test_delete_booking_requires_csrf(client, db_path, make_user, seeded_showing):
    owner = make_user(email="owner2@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)
    login_session(client, owner["email"])
    resp = client.post("/delete", data={"booking_id": bookingid})
    assert resp.status_code == 403


def test_delete_booking_succeeds_for_owner(client, db_path, make_user, seeded_showing):
    owner = make_user(email="owner3@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)
    token = login_session(client, owner["email"])
    resp = client.post("/delete", data={"booking_id": bookingid, "csrf_token": token})
    assert resp.status_code == 302

    conn = sqlite3.connect(db_path)
    exists = conn.execute("SELECT 1 FROM booking WHERE bookingid = ?", (bookingid,)).fetchone()
    conn.close()
    assert exists is None


def test_edit_page_blocks_non_owner(client, db_path, make_user, seeded_showing):
    owner = make_user(email="owner4@example.com")
    attacker = make_user(email="attacker2@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)

    login_session(client, attacker["email"])
    resp = client.post("/edit", data={"booking_id": bookingid})
    assert resp.status_code == 403


def test_edit_confirm_blocks_non_owner(client, db_path, make_user, seeded_showing):
    owner = make_user(email="owner5@example.com")
    attacker = make_user(email="attacker3@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)

    token = login_session(client, attacker["email"])
    resp = client.post("/edit/confirm", data={
        "seats": [f"{seat_id} {bookingid}"], "other-info": "", "csrf_token": token,
    })
    assert resp.status_code == 403


def test_edit_confirm_updates_seats_and_info_for_owner(client, db_path, make_user, seeded_showing):
    owner = make_user(email="editor@example.com")
    seat_ids = get_seat_ids(db_path, seeded_showing["showing_id"], limit=2)
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_ids[0])

    token = login_session(client, owner["email"])
    new_seat = seat_ids[1]
    resp = client.post("/edit/confirm", data={
        "seats": [f"{new_seat} {bookingid}"],
        "other-info": "updated info",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/account"

    conn = sqlite3.connect(db_path)
    seats_after = {
        row[0] for row in conn.execute(
            "SELECT seatid FROM bookingdetail WHERE bookingid = ?", (bookingid,)
        ).fetchall()
    }
    otherinfo = conn.execute(
        "SELECT otherinfo FROM booking WHERE bookingid = ?", (bookingid,)
    ).fetchone()[0]
    conn.close()
    assert seats_after == {new_seat}
    assert otherinfo == "updated info"


def test_edit_confirm_rejects_seat_booked_by_another_booking(client, db_path, make_user, seeded_showing):
    owner = make_user(email="editor2@example.com")
    other_user = make_user(email="otheruser@example.com")
    seat_ids = get_seat_ids(db_path, seeded_showing["showing_id"], limit=2)
    my_bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_ids[0])
    create_booking_directly(db_path, other_user["userid"], seeded_showing["showing_id"], seat_ids[1])

    token = login_session(client, owner["email"])
    resp = client.post("/edit/confirm", data={
        "seats": [f"{seat_ids[1]} {my_bookingid}"],
        "other-info": "",
        "csrf_token": token,
    })
    assert resp.status_code == 409


def test_edit_confirm_allows_keeping_own_already_booked_seat(client, db_path, make_user, seeded_showing):
    """A booking's own existing seat shouldn't be treated as 'taken' when re-submitted unchanged."""
    owner = make_user(email="editor3@example.com")
    seat_id = get_seat_ids(db_path, seeded_showing["showing_id"], limit=1)[0]
    bookingid = create_booking_directly(db_path, owner["userid"], seeded_showing["showing_id"], seat_id)

    token = login_session(client, owner["email"])
    resp = client.post("/edit/confirm", data={
        "seats": [f"{seat_id} {bookingid}"],
        "other-info": "",
        "csrf_token": token,
    })
    assert resp.status_code == 302


def test_edit_confirm_rejects_past_showing(client, db_path, make_user):
    owner = make_user(email="editorpast@example.com")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO showing (filmid, screenid, datetime) VALUES (1, 10, '2020-01-01 14:05')")
    conn.commit()
    past_showing_id = conn.execute(
        "SELECT showingid FROM showing WHERE screenid = 10 AND datetime = '2020-01-01 14:05'"
    ).fetchone()[0]
    seat_id = get_seat_ids(db_path, past_showing_id, limit=1)[0]
    conn.close()
    bookingid = create_booking_directly(db_path, owner["userid"], past_showing_id, seat_id)

    token = login_session(client, owner["email"])
    resp = client.post("/edit/confirm", data={
        "seats": [f"{seat_id} {bookingid}"],
        "other-info": "",
        "csrf_token": token,
    })
    assert resp.status_code == 410
