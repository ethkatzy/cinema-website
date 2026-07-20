import main


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_session_cookie_is_httponly_and_samesite(client):
    resp = client.get("/login")
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_secret_key_is_not_the_old_hardcoded_value():
    import config
    assert config.secret_key != "39e5b8dd1de7afdc786df2b0cdf7a8f1"
    assert len(config.secret_key) >= 32


def test_check_csrf_rejects_missing_session_token(client):
    with client.session_transaction() as sess:
        sess.pop("csrf_token", None)
    resp = client.post("/create", data={
        "username": "x", "password_1": "x", "password_2": "x",
        "email": "x@example.com", "phone_number": "0700", "csrf_token": "guessed-token",
    })
    assert resp.status_code == 403


def test_check_csrf_rejects_mismatched_token(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "real-token"
    resp = client.post("/create", data={
        "username": "x", "password_1": "x", "password_2": "x",
        "email": "x2@example.com", "phone_number": "0700", "csrf_token": "wrong-token",
    })
    assert resp.status_code == 403


def test_secure_cookie_flag_tracks_production_mode():
    assert main.app.config["SESSION_COOKIE_SECURE"] == main.IS_PRODUCTION
