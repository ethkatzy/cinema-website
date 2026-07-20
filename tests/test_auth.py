import sqlite3

from conftest import csrf_token_from_get, login_session


def test_signup_creates_account_and_logs_in(client):
    token = csrf_token_from_get(client, "/signup")
    resp = client.post("/create", data={
        "username": "New User",
        "password_1": "Sup3rSecret!",
        "password_2": "Sup3rSecret!",
        "email": "newuser@example.com",
        "phone_number": "07123456789",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    with client.session_transaction() as sess:
        assert sess["email"] == "newuser@example.com"


def test_signup_password_mismatch_does_not_create_account(client, db_path):
    token = csrf_token_from_get(client, "/signup")
    resp = client.post("/create", data={
        "username": "New User",
        "password_1": "Sup3rSecret!",
        "password_2": "Different!",
        "email": "mismatch@example.com",
        "phone_number": "07123456789",
        "csrf_token": token,
    })
    assert resp.status_code == 200
    assert b"Passwords don" in resp.data
    with client.session_transaction() as sess:
        assert "email" not in sess
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM user WHERE email = ?", ("mismatch@example.com",)
    ).fetchone()[0]
    conn.close()
    assert count == 0


def test_signup_duplicate_email_rejected(client, make_user):
    user = make_user(email="dupe@example.com")
    token = csrf_token_from_get(client, "/signup")
    resp = client.post("/create", data={
        "username": "Another",
        "password_1": "Whatever1!",
        "password_2": "Whatever1!",
        "email": user["email"],
        "phone_number": "07000000001",
        "csrf_token": token,
    })
    assert resp.status_code == 200
    assert b"already has an account" in resp.data


def test_signup_without_csrf_token_is_rejected(client):
    resp = client.post("/create", data={
        "username": "No CSRF",
        "password_1": "Password1!",
        "password_2": "Password1!",
        "email": "nocsrf@example.com",
        "phone_number": "0700",
    })
    assert resp.status_code == 403


def test_login_success(client, make_user):
    user = make_user(email="login@example.com", password="CorrectHorse1!")
    token = csrf_token_from_get(client, "/login")
    resp = client.post("/login/attempt", data={
        "email": user["email"], "password": user["password"], "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    with client.session_transaction() as sess:
        assert sess["email"] == user["email"]


def test_login_invalid_credentials_shows_message(client, make_user):
    user = make_user(email="badpass@example.com", password="CorrectHorse1!")
    token = csrf_token_from_get(client, "/login")
    resp = client.post("/login/attempt", data={
        "email": user["email"], "password": "wrong-password", "csrf_token": token,
    })
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
    with client.session_transaction() as sess:
        assert "email" not in sess


def test_login_without_csrf_token_is_rejected(client, make_user):
    user = make_user(email="nocsrf-login@example.com")
    resp = client.post("/login/attempt", data={"email": user["email"], "password": "x"})
    assert resp.status_code == 403


def _current_csrf_token(client):
    # login_attempt() rotates the CSRF token on every failed submission (same
    # pattern used elsewhere in the app), so each resubmission needs a fresh read.
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def test_login_rate_limited_after_five_failures(client, make_user):
    user = make_user(email="ratelimited@example.com", password="Correct1!")
    csrf_token_from_get(client, "/login")
    for _ in range(5):
        resp = client.post("/login/attempt", data={
            "email": user["email"], "password": "wrong", "csrf_token": _current_csrf_token(client),
        })
        assert resp.status_code == 200

    resp = client.post("/login/attempt", data={
        "email": user["email"], "password": "wrong", "csrf_token": _current_csrf_token(client),
    })
    assert resp.status_code == 429

    # even the correct password is locked out once the limit is hit
    resp = client.post("/login/attempt", data={
        "email": user["email"], "password": user["password"],
        "csrf_token": _current_csrf_token(client),
    })
    assert resp.status_code == 429


def test_login_rate_limit_is_scoped_per_email(client, make_user):
    victim = make_user(email="victim@example.com", password="Correct1!")
    attacker_email = "someone-else@example.com"
    csrf_token_from_get(client, "/login")
    for _ in range(5):
        client.post("/login/attempt", data={
            "email": attacker_email, "password": "wrong", "csrf_token": _current_csrf_token(client),
        })

    resp = client.post("/login/attempt", data={
        "email": victim["email"], "password": victim["password"],
        "csrf_token": _current_csrf_token(client),
    })
    assert resp.status_code == 302


def test_logout_clears_session(client, make_user):
    user = make_user(email="logout@example.com")
    login_session(client, user["email"])
    resp = client.get("/logout")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "email" not in sess


def test_logout_when_not_logged_in_does_not_error(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
