import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

from flask import Flask, render_template, request, redirect, session, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import config

app = Flask(__name__)
app.secret_key = config.secret_key

IS_PRODUCTION = os.environ.get("FLASK_ENV", "development") != "development"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION

DB_PATH = "CinemaDatabase.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
TICKET_PRICE = 8.99

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 300
_login_attempts = defaultdict(list)


def init_db_if_needed():
    if os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="cp1252"))


def get_db():
    return sqlite3.connect(DB_PATH)


init_db_if_needed()


def check_csrf():
    token = request.form.get("csrf_token")
    if not token or token != session.get("csrf_token"):
        abort(403)


def check_login_rate_limit(key):
    now = time.time()
    attempts = [t for t in _login_attempts[key] if now - t < LOGIN_ATTEMPT_WINDOW_SECONDS]
    _login_attempts[key] = attempts
    if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
        abort(429)


def record_login_failure(key):
    _login_attempts[key].append(time.time())


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def issue_csrf_token():
    session["csrf_token"] = secrets.token_hex(16)


def require_login():
    if "email" not in session:
        issue_csrf_token()
        return render_template("login.html")
    return None


def get_user_by_email(cursor, email):
    cursor.execute("SELECT userid, username FROM user WHERE email = ?", (email,))
    return cursor.fetchone()


def get_owned_booking(cursor, booking_id, email):
    cursor.execute("""SELECT b.bookingid, b.showingid FROM booking b
                    JOIN user u ON b.userid = u.userid
                    WHERE b.bookingid = ? AND u.email = ?""", (booking_id, email))
    row = cursor.fetchone()
    if row is None:
        abort(403)
    return row


def get_seats_for_showing(cursor, showing_id):
    cursor.execute("""SELECT seatid, rownum, seatnum FROM seat WHERE screenid =
        (SELECT screenid FROM showing WHERE showingid = ?)""", (showing_id,))
    return [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]


def get_booked_seat_ids(cursor, showing_id, exclude_booking_id=None):
    if exclude_booking_id is None:
        cursor.execute("""SELECT seatid FROM bookingdetail WHERE bookingid IN
            (SELECT bookingid FROM booking WHERE showingid = ?)""", (showing_id,))
    else:
        cursor.execute("""SELECT seatid FROM bookingdetail WHERE bookingid IN
            (SELECT bookingid FROM booking
            WHERE showingid = ? AND bookingid != ?)""", (showing_id, exclude_booking_id))
    return {row[0] for row in cursor.fetchall()}


def get_showing_details(cursor, showing_id):
    cursor.execute("""SELECT f.title, s.datetime FROM showing s JOIN film f ON f.filmid = s.filmid
        WHERE s.showingid = ?""", (showing_id,))
    return cursor.fetchall()


def validate_seat_selection(selected_seat_ids, valid_seat_ids, booked_seat_ids):
    if not selected_seat_ids <= valid_seat_ids or selected_seat_ids & booked_seat_ids:
        abort(409)


@app.route('/')
def index():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT f.filmid, f.title, f.description, r.icon, f.rating, f.posterurl FROM film f
                       JOIN ratingicon r ON f.rating = r.rating""")
        results = cursor.fetchall()
        cursor.execute("SELECT showingid, filmid, screenid, datetime FROM showing WHERE date(datetime) = ?",
                       ("2025-01-18",))
        showings = cursor.fetchall()
    return render_template("index.html", items=results, showings=showings)


@app.route("/<int:film_id>")
def film_page(film_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT f.title, f.description, f.duration, f.releasedate, r.icon, f.posterurl,
         f.actors, f.director, f.rating FROM film f JOIN ratingicon r ON r.rating = f.rating WHERE filmId = ?""",
                       (film_id,))
        film = cursor.fetchone()
        cursor.execute("SELECT showingid, screenid, datetime FROM showing WHERE filmid = ?",
                       (film_id,))
        showings = cursor.fetchall()
        if not film:
            abort(404)
        showings_by_date = {}
        for showing in showings:
            date = showing[2][:10]
            showings_by_date.setdefault(date, []).append(showing)
        runtime = int(film[2])
        return render_template("film.html", film=film, showings_by_date=showings_by_date,
                               runtime=runtime)


@app.route("/signup")
def signup():
    if "email" in session:
        return redirect("/")
    issue_csrf_token()
    return render_template("signup.html")


@app.route("/create", methods=["POST"])
def create():
    if "email" in session:
        return redirect("/")
    check_csrf()
    username = request.form["username"]
    password_1 = request.form["password_1"]
    password_2 = request.form["password_2"]
    email = request.form["email"]
    phone_number = request.form["phone_number"]
    if password_1 != password_2:
        issue_csrf_token()
        message = "Passwords don't match"
        return render_template("signup.html", message=message)
    password_hash = generate_password_hash(password_1)
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO user (username, email, phonenumber, passwordhash) VALUES (?, ?, ?, ?)",
                           (username, email, phone_number, password_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            issue_csrf_token()
            message = "That email already has an account"
            return render_template("signup.html", message=message)
        session["email"] = email
        return redirect("/")


@app.route("/login/attempt", methods=["POST"])
def login_attempt():
    if "email" in session:
        return redirect("/")
    check_csrf()
    email = request.form["email"]
    password = request.form["password"]
    rate_limit_key = (request.remote_addr, email)
    check_login_rate_limit(rate_limit_key)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT passwordhash FROM user WHERE email = ?", (email,))
        user_account = cursor.fetchone()
        if user_account is not None and check_password_hash(user_account[0], password):
            session["email"] = email
            return redirect("/")
        record_login_failure(rate_limit_key)
        issue_csrf_token()
        return render_template("login.html", message="Invalid email or password")


@app.route("/login")
def login():
    if "email" not in session:
        issue_csrf_token()
        return render_template("login.html")
    return redirect("/")


@app.route("/logout")
def logout():
    session.pop("email", None)
    return redirect("/")


def render_showing_page(showing_id, error=None):
    with get_db() as conn:
        cursor = conn.cursor()
        seats = get_seats_for_showing(cursor, showing_id)
        booked_seat_ids = get_booked_seat_ids(cursor, showing_id)
        details = get_showing_details(cursor, showing_id)
        issue_csrf_token()
        context = {"seats": seats, "booked_seat_ids": booked_seat_ids, "details": details}
        if error is not None:
            context["error"] = error
        return render_template("showing.html", **context)


@app.route("/showing/<int:showing_id>", methods=["POST", "GET"])
def booking(showing_id):
    if request.method != "POST":
        return render_showing_page(showing_id)

    selected_seats = request.form.getlist("seats")
    if not selected_seats:
        check_csrf()
        return render_showing_page(showing_id, error="Please select at least one seat!")

    resp = require_login()
    if resp:
        return resp

    with get_db() as conn:
        check_csrf()
        cursor = conn.cursor()
        seats = get_seats_for_showing(cursor, showing_id)
        valid_seat_ids = {seat["seatid"] for seat in seats}
        booked_seat_ids = get_booked_seat_ids(cursor, showing_id)
        try:
            selected_seat_ids = {int(seat_id) for seat_id in selected_seats}
        except ValueError:
            abort(400)
        validate_seat_selection(selected_seat_ids, valid_seat_ids, booked_seat_ids)

        userid, _ = get_user_by_email(cursor, session["email"])
        other_info = request.form.getlist("other-info")[0]
        cursor.execute("""INSERT INTO booking (userid, showingid, bookingtime, totalprice, otherinfo) VALUES
        (?, ?, datetime('now'), ?, ?)""",
                       (userid, showing_id, TICKET_PRICE * len(selected_seat_ids), other_info))
        booking_id = cursor.lastrowid
        cursor.executemany("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)",
                            [(booking_id, seat_id) for seat_id in selected_seat_ids])
        conn.commit()
    return redirect("/account")


@app.route("/account")
def account():
    resp = require_login()
    if resp:
        return resp
    with get_db() as conn:
        cursor = conn.cursor()
        userid, username = get_user_by_email(cursor, session["email"])
        cursor.execute("""SELECT f.title, GROUP_CONCAT(se.rownum || se.seatnum, ', '), s.datetime, s.screenid,
        b.bookingid AS booked_seats, b.totalprice, b.otherinfo
        FROM booking b
        JOIN bookingdetail bd ON b.bookingid = bd.bookingid
        JOIN showing s ON b.showingid = s.showingid
        JOIN film f ON s.filmid = f.filmid
        JOIN seat se ON bd.seatid = se.seatid
        WHERE b.userid = ?
        GROUP BY b.bookingid, f.title;""", (userid,))
        bookings = cursor.fetchall()
        issue_csrf_token()
        return render_template("account.html", bookings=bookings, name=username)


@app.route("/delete", methods=["POST"])
def delete():
    check_csrf()
    resp = require_login()
    if resp:
        return resp
    booking_id = request.form["booking_id"]
    with get_db() as conn:
        cursor = conn.cursor()
        get_owned_booking(cursor, booking_id, session["email"])
        cursor.execute("DELETE FROM booking WHERE bookingid = ?", (booking_id,))
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        conn.commit()
    return redirect("/account")


@app.route("/search", methods=["POST", "GET"])
def search():
    showings = []
    with get_db() as conn:
        cursor = conn.cursor()
        if request.method == "POST":
            film = request.form["film"]
            day = request.form["day"]
            user_search = (film, day)
            if not (film == "All films") and not (day == "All days"):
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE f.title = ? AND date(s.datetime) = ? ORDER BY s.datetime;""",
                               [film, day])
                showings = cursor.fetchall()
                search_type = 1
            elif film == "All films" and not (day == "All days"):
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE date(s.datetime) = ? ORDER BY s.datetime;""",
                               [day])
                showings = cursor.fetchall()
                search_type = 2
            elif not (film == "All films") and day == "All days":
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE f.title = ? ORDER BY s.datetime;""", [film])
                showings = cursor.fetchall()
                search_type = 3
            else:
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid ORDER BY s.datetime;""")
                showings = cursor.fetchall()
                search_type = 4
        cursor.execute("SELECT title, filmid FROM film")
        films = cursor.fetchall()
        cursor.execute("SELECT DISTINCT date(datetime) FROM showing")
        days = cursor.fetchall()
        if "email" in session:
            name = get_user_by_email(cursor, session["email"])[1]
        else:
            name = ""
        issue_csrf_token()
        if not (showings == []):
            return render_template("search.html", films=films, days=days, showings=showings,
                                   search=user_search, search_type=search_type)
        return render_template("search.html", films=films, days=days, search_type=0, name=name)


def render_edit_page(error=None):
    booking_id = request.form["booking_id"]
    with get_db() as conn:
        cursor = conn.cursor()
        _, showing_id = get_owned_booking(cursor, booking_id, session["email"])
        seats = get_seats_for_showing(cursor, showing_id)
        booked_seat_ids = get_booked_seat_ids(cursor, showing_id)
        cursor.execute("SELECT seatid FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        user_seats = {row[0] for row in cursor.fetchall()}
        details = get_showing_details(cursor, showing_id)
        issue_csrf_token()
        return render_template("edit.html", seats=seats, booked_seat_ids=booked_seat_ids,
                               user_seats=user_seats, error=error, booking_id=booking_id, details=details)


@app.route("/edit", methods=["POST"])
def edit():
    resp = require_login()
    if resp:
        return resp
    return render_edit_page()


@app.route("/edit/confirm", methods=["POST"])
def edit_confirm():
    check_csrf()
    resp = require_login()
    if resp:
        return resp
    selected_seats = request.form.getlist("seats")
    if not selected_seats:
        return render_edit_page(error="Please select at least one seat!")
    booking_id = selected_seats[0].split()[1]
    other_info = request.form.getlist("other-info")[0]
    with get_db() as conn:
        cursor = conn.cursor()
        _, showing_id = get_owned_booking(cursor, booking_id, session["email"])
        seats = get_seats_for_showing(cursor, showing_id)
        valid_seat_ids = {seat["seatid"] for seat in seats}
        booked_seat_ids = get_booked_seat_ids(cursor, showing_id, exclude_booking_id=booking_id)
        try:
            selected_seat_ids = {int(seat.split()[0]) for seat in selected_seats}
        except ValueError:
            abort(400)
        validate_seat_selection(selected_seat_ids, valid_seat_ids, booked_seat_ids)
        cursor.execute("""UPDATE booking SET bookingtime = datetime('now'), totalprice = ?, otherinfo = ?
        WHERE bookingid = ?""", (TICKET_PRICE * len(selected_seat_ids), other_info, booking_id))
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        cursor.executemany("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)",
                            [(booking_id, seat_id) for seat_id in selected_seat_ids])
        conn.commit()
    return redirect("/account")


if __name__ == '__main__':
    app.run(debug=not IS_PRODUCTION)
