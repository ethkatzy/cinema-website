import secrets

from flask import Flask, render_template, request, redirect, session, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import config

app = Flask(__name__)
app.secret_key = config.secret_key


def check_csrf():
    if request.form["csrf_token"] != session["csrf_token"]:
        abort(403)


@app.route('/')
def index():
    with sqlite3.connect("CinemaDatabase.db") as conn:
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
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT f.title, f.description, f.duration, f.releasedate, r.icon, f.posterurl,
         f.actors, f.director, f.rating FROM film f JOIN ratingicon r ON r.rating = f.rating WHERE filmId = ?""",
                       (film_id,))
        film = cursor.fetchone()
        showings = cursor.execute("SELECT showingid, screenid, datetime FROM showing WHERE filmid = ?",
                                  (film_id,))
        if film:
            showings_by_date = {}
            for showing in showings:
                date = showing[2][:10]
                if date not in showings_by_date:
                    showings_by_date[date] = []
                showings_by_date[date].append(showing)
            runtime = int(film[2])
        return render_template("film.html", film=film, showings_by_date=showings_by_date,
                               runtime=runtime)


@app.route("/signup")
def signup():
    if "email" in session:
        return redirect("/")
    return render_template("signup.html")


@app.route("/create", methods=["POST"])
def create():
    if "email" in session:
        return redirect("/")
    username = request.form["username"]
    password_1 = request.form["password_1"]
    password_2 = request.form["password_2"]
    email = request.form["email"]
    phone_number = request.form["phone_number"]
    if password_1 != password_2:
        message = "Passwords don't match"
        return render_template("signup.html", message=message)
    password_hash = generate_password_hash(password_1)
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO user (username, email, phonenumber, passwordhash) VALUES (?, ?, ?, ?)",
                           (username, email, phone_number, password_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            message = "That email already has an account"
            return render_template("signup.html", message=message)
        session["email"] = email
        return redirect("/")


@app.route("/login/attempt", methods=["POST"])
def login_attempt():
    if "email" in session:
        return redirect("/")
    try:
        email = request.form["email"]
        password = request.form["password"]
        with sqlite3.connect("CinemaDatabase.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT passwordhash FROM user WHERE email = ?", (email,))
            user_account = cursor.fetchone()
            if check_password_hash(user_account[0], password):
                session["email"] = email
                return redirect("/")
            else:
                return render_template("login.html", message="Invalid email or password")
    except TypeError:
        return render_template("login.html", message="Invalid email or password")


@app.route("/login")
def login():
    if not ("email" in session):
        return render_template("login.html")
    return redirect("/")


@app.route("/logout")
def logout():
    del session["email"]
    return redirect("/")


@app.route("/showing/<int:showing_id>", methods=["POST", "GET"])
def booking(showing_id):
    if request.method == "POST":
        selected_seats = request.form.getlist("seats")
        if not selected_seats:
            check_csrf()
            error = "Please select at least one seat!"
            with sqlite3.connect("CinemaDatabase.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT seatid, rownum, seatnum FROM seat WHERE screenid = 
                    (SELECT screenid FROM showing WHERE showingid = ?)""", (showing_id,))
                seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]
                cursor.execute("""SELECT seatid FROM bookingdetail WHERE bookingid IN 
                (SELECT bookingid FROM booking WHERE showingid = ?)""", (showing_id,))
                booked_seat_ids = {row[0] for row in cursor.fetchall()}
                cursor.execute("""SELECT f.title, s.datetime FROM showing s JOIN film f ON f.filmid = s.filmid 
                                        WHERE s.showingid = ?""", [showing_id, ])
                details = cursor.fetchall()
                session["csrf_token"] = secrets.token_hex(16)
                return render_template("showing.html", seats=seats, booked_seat_ids=booked_seat_ids,
                                       details=details, error=error)
        elif not ("email" in session):
            return render_template("login.html")
        with sqlite3.connect("CinemaDatabase.db") as conn:
            check_csrf()
            cursor = conn.cursor()
            cursor.execute("SELECT userid FROM user WHERE email = ?", (session["email"],))
            userid = cursor.fetchone()[0]
            other_info = request.form.getlist("other-info")[0]
            cursor.execute("""INSERT INTO booking (userid, showingid, bookingtime, totalprice, otherinfo) VALUES 
            (?, ?, datetime('now'), ?, ?)""", (userid, showing_id, 8.99 * len(selected_seats), other_info))
            booking_id = cursor.lastrowid
            for seat_id in selected_seats:
                cursor.execute("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)",
                               (booking_id, seat_id))
            conn.commit()
            seats = []
            for seat_id in selected_seats:
                cursor.execute("SELECT rownum, seatnum FROM seat WHERE seatid = ?", (seat_id,))
                seat = cursor.fetchone()
                seats.append(seat[0] + str(seat[1]))
        return redirect("/account")
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT seatid, rownum, seatnum FROM seat WHERE screenid = 
        (SELECT screenid FROM showing WHERE showingid = ?)""", (showing_id,))
        seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]
        cursor.execute("""SELECT seatid FROM bookingdetail WHERE bookingid IN 
        (SELECT bookingid FROM booking WHERE showingid = ?)""", (showing_id,))
        booked_seat_ids = {row[0] for row in cursor.fetchall()}
        cursor.execute("""SELECT f.title, s.datetime FROM showing s JOIN film f ON f.filmid = s.filmid 
        WHERE s.showingid = ?""", [showing_id, ])
        details = cursor.fetchall()
        session["csrf_token"] = secrets.token_hex(16)
        return render_template("showing.html", seats=seats, booked_seat_ids=booked_seat_ids,
                           details=details)


@app.route("/account")
def account():
    if "email" in session:
        with sqlite3.connect("CinemaDatabase.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT userid, username FROM user WHERE email = ?", (session["email"],))
            user = cursor.fetchone()
            cursor.execute("""SELECT f.title, GROUP_CONCAT(se.rownum || se.seatnum, ', '), s.datetime, s.screenid, 
            b.bookingid AS booked_seats, b.totalprice, b.otherinfo
            FROM booking b
            JOIN bookingdetail bd ON b.bookingid = bd.bookingid
            JOIN showing s ON b.showingid = s.showingid
            JOIN film f ON s.filmid = f.filmid
            JOIN seat se ON bd.seatid = se.seatid
            WHERE b.userid = ?
            GROUP BY b.bookingid, f.title;""", (user[0],))
            bookings = cursor.fetchall()
            session["csrf_token"] = secrets.token_hex(16)
            return render_template("account.html", bookings=bookings, name=user[1])
    else:
        return render_template("login.html")


@app.route("/delete", methods=["POST"])
def delete():
    check_csrf()
    booking_id = request.form["booking_id"]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM booking WHERE bookingid = ?", (booking_id,))
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        conn.commit()
    return redirect("/account")


@app.route("/search", methods=["POST", "GET"])
def search():
    showings = []
    with sqlite3.connect("CinemaDatabase.db") as conn:
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
            cursor.execute("SELECT username FROM user WHERE email = ?", (session["email"],))
            name = cursor.fetchone()[0]
        else:
            name = ""
        session["csrf_token"] = secrets.token_hex(16)
        if not (showings == []):
            return render_template("search.html", films=films, days=days, showings=showings,
                                   search=user_search, search_type=search_type)
        return render_template("search.html", films=films, days=days, search_type=0, name=name)


@app.route("/edit", methods=["POST"])
def edit(error=None):
    booking_id = request.form["booking_id"]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT showingid FROM booking WHERE bookingid = ?", (booking_id,))
        showing_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT seatid, rownum, seatnum FROM seat WHERE screenid = "
            "(SELECT screenid FROM showing WHERE showingid = ?)", (showing_id,))
        seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]
        cursor.execute(
            "SELECT seatid FROM bookingdetail WHERE bookingid IN "
            "(SELECT bookingid FROM booking WHERE showingid = ?)", (showing_id,))
        booked_seat_ids = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT seatid FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        user_seats = {row[0] for row in cursor.fetchall()}
        cursor.execute("""SELECT f.title, s.datetime FROM showing s JOIN film f ON f.filmid = s.filmid 
                                        WHERE s.showingid = ?""", [showing_id, ])
        details = cursor.fetchall()
        session["csrf_token"] = secrets.token_hex(16)
        return render_template("edit.html", seats=seats, booked_seat_ids=booked_seat_ids,
                               user_seats=user_seats, error=error, booking_id=booking_id, details=details)


@app.route("/edit/confirm", methods=["POST"])
def edit_confirm():
    check_csrf()
    selected_seats = request.form.getlist("seats")
    if not selected_seats:
        error = "Please select at least one seat!"
        return edit(error)
    booking_id = selected_seats[0].split()[1]
    other_info = request.form.getlist("other-info")[0]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""UPDATE booking SET bookingtime = datetime('now'), totalprice = ?, otherinfo = ? 
        WHERE bookingid = ?""", [len(selected_seats) * 8.99, other_info, booking_id])
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (booking_id,))
        for seat in selected_seats:
            cursor.execute("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)",
                           [booking_id, seat.split()[0]])
        conn.commit()
    return redirect("/account")


if __name__ == '__main__':
    app.run(debug=True)
