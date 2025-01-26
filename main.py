from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import config

app = Flask(__name__)
app.secret_key = config.secret_key


@app.route('/')
def index():
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM film")
        results = cursor.fetchall()
        cursor.execute("SELECT * FROM showing WHERE date(datetime) = ?", ("2025-01-18",))
        showings = cursor.fetchall()
        if "email" in session:
            cursor.execute("SELECT username FROM user WHERE email = ?", (session["email"],))
            name = cursor.fetchone()[0]
        else:
            name = ""
    return render_template("index.html", items=results, message=name, showings=showings)


@app.route("/<int:film_id>")
def film_page(film_id):
    # Fetch film details from the database
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM film WHERE filmId = ?", (film_id,))
        film = cursor.fetchone()
        showings = cursor.execute("SELECT * FROM showing WHERE filmid = ?", (film_id,))
    if film:
        showings_by_date = {}
        for showing in showings:
            date = showing[3][:10]  # Extract date from datetime string
            if date not in showings_by_date:
                showings_by_date[date] = []
            showings_by_date[date].append(showing)
        return render_template("film.html", film=film, showings_by_date=showings_by_date)
    else:
        # Redirect to "no film here" page if filmId doesn't exist
        return redirect(url_for("no_film"))


@app.route("/signup")
def signup():
    return render_template("signup.html")


@app.route("/create", methods=["POST"])
def create():
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]
    email = request.form["email"]
    phoneNumber = request.form["phonenumber"]
    if password1 != password2:
        return "Passwords don't match"
    password_hash = generate_password_hash(password1)

    try:
        with sqlite3.connect("CinemaDatabase.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO user (username, email, phonenumber, passwordhash) VALUES (?, ?, ?, ?)",
                           (username, email, phoneNumber, password_hash))
    except sqlite3.IntegrityError:
        return "That email already has an account"

    db = sqlite3.connect('CinemaDatabase.db')
    result = db.execute('SELECT * FROM film')
    return render_template("index.html", items=result, message=username)


@app.route("/login1", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT passwordhash FROM user WHERE email = ?", (email,))
        account = cursor.fetchone()
        if check_password_hash(account[0], password):
            session["email"] = email
            return redirect("/")
        else:
            return render_template("login.html", message="Invalid email or password")


@app.route("/login")
def login1():
    return render_template("login.html")


@app.route("/logout")
def logout():
    del session["email"]
    return redirect("/")


@app.route("/showing/<int:showing_id>", methods=["POST", "GET"])
def booking(showing_id):
    if request.method == "POST":
        selectedSeats = request.form.getlist("seats")
        if not selectedSeats:
            error = "Please select at least one seat!"
            with sqlite3.connect("CinemaDatabase.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT seatid, rownum, seatnum FROM seat WHERE screenid = (SELECT screenid FROM showing WHERE showingid = ?)",
                    (showing_id,))
                seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT seatid FROM bookingdetail WHERE bookingid IN (SELECT bookingid FROM booking WHERE showingid = ?)",
                    (showing_id,))
                bookedSeatIds = {row[0] for row in cursor.fetchall()}

            return render_template("showing.html", seats=seats, bookedSeatIds=bookedSeatIds, showingId=showing_id,
                                   error=error)
        elif not ("email" in session):
            return render_template("login.html")
        with sqlite3.connect("CinemaDatabase.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT userid FROM user WHERE email = ?", (session["email"],))
            userid = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO booking (userid, showingid, bookingtime, totalprice) VALUES (?, ?, datetime('now'), ?)",
                (userid, showing_id, 8.99 * len(selectedSeats)))
            bookingId = cursor.lastrowid
            # Insert seats into the bookingdetail table
            for seatId in selectedSeats:
                cursor.execute("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)", (bookingId, seatId))
            conn.commit()
            seats = []
            for seatId in selectedSeats:
                cursor.execute("SELECT rownum, seatnum FROM seat WHERE seatid = ?", (seatId,))
                seat = cursor.fetchone()
                seats.append(seat[0] + str(seat[1]))

        return render_template("booking_success.html", selectedSeats=seats,
                               totalPrice=8.99 * len(selectedSeats))

    # Fetch seat layout and availability
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT seatid, rownum, seatnum FROM seat WHERE screenid = (SELECT screenid FROM showing WHERE showingid = ?)",
            (showing_id,))
        seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]

        cursor.execute(
            "SELECT seatid FROM bookingdetail WHERE bookingid IN (SELECT bookingid FROM booking WHERE showingid = ?)",
            (showing_id,))
        bookedSeatIds = {row[0] for row in cursor.fetchall()}

    return render_template("showing.html", seats=seats, bookedSeatIds=bookedSeatIds, showingId=showing_id)


@app.route("/account")
def account():
    if "email" in session:
        with sqlite3.connect("CinemaDatabase.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT userid FROM user WHERE email = ?", (session["email"],))
            userid = cursor.fetchone()[0]
            cursor.execute("""SELECT f.title, GROUP_CONCAT(se.rownum || se.seatnum), s.datetime, s.screenid, b.bookingid AS booked_seats
            FROM booking b
            JOIN bookingdetail bd ON b.bookingid = bd.bookingid
            JOIN showing s ON b.showingid = s.showingid
            JOIN film f ON s.filmid = f.filmid
            JOIN seat se ON bd.seatid = se.seatid
            WHERE b.userid = ?
            GROUP BY b.bookingid, f.title;""", (userid,))
            bookings = cursor.fetchall()
            return render_template("account.html", bookings=bookings)
    else:
        return render_template("login.html")


@app.route("/delete", methods=["POST"])
def delete():
    bookingid = request.form["bookingid"]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM booking WHERE bookingid = ?", (bookingid,))
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (bookingid,))
        conn.commit()
    return account()


@app.route("/search", methods=["POST", "GET"])
def search():
    showings = []
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        if request.method == "POST":
            film = request.form["film"]
            day = request.form["day"]
            search = (film, day)
            if not (film == "All films") and not (day == "All days"):
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE f.title = ? AND date(s.datetime) = ? ORDER BY s.datetime;"""
                               , [film, day])
                showings = cursor.fetchall()
            elif film == "All films" and not (day == "All days"):
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE date(s.datetime) = ? ORDER BY s.datetime;"""
                               , [day])
                showings = cursor.fetchall()
            elif not (film == "All films") and day == "All days":
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid WHERE f.title = ? ORDER BY s.datetime;"""
                               , [film])
                showings = cursor.fetchall()
            else:
                cursor.execute("""SELECT f.title, s.datetime, s.screenid, s.showingid, f.filmid FROM showing s
                JOIN film f ON f.filmid = s.filmid ORDER BY s.datetime;""")
                showings = cursor.fetchall()

        cursor.execute("SELECT title, filmid FROM film")
        films = cursor.fetchall()
        cursor.execute("SELECT DISTINCT date(datetime) FROM showing")
        days = cursor.fetchall()
        if not (showings == []):
            return render_template("search.html", films=films, days=days, showings=showings, search=search)
        return render_template("search.html", films=films, days=days)


@app.route("/edit", methods=["POST"])
def edit(error=None):
    bookingid = request.form["bookingid"]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT showingid FROM booking WHERE bookingid = ?", (bookingid,))
        showing_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT seatid, rownum, seatnum FROM seat WHERE screenid = (SELECT screenid FROM showing WHERE showingid = ?)",
            (showing_id,))
        seats = [{"seatid": row[0], "rownum": row[1], "seatnum": row[2]} for row in cursor.fetchall()]
        cursor.execute(
            "SELECT seatid FROM bookingdetail WHERE bookingid IN (SELECT bookingid FROM booking WHERE showingid = ?)",
            (showing_id,))
        bookedSeatIds = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT seatid FROM bookingdetail WHERE bookingid = ?", (bookingid,))
        userSeats = {row[0] for row in cursor.fetchall()}
        return render_template("edit.html", seats=seats, bookedSeatIds=bookedSeatIds, userSeats=userSeats, error=error, bookingid=bookingid)


@app.route("/edit/confirm", methods=["POST"])
def editconfirm():
    selectedSeats = request.form.getlist("seats")
    if not selectedSeats:
        error = "Please select at least one seat!"
        return edit(error)
    bookingid = selectedSeats[0].split()[1]
    with sqlite3.connect("CinemaDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE booking SET bookingtime = datetime('now'), totalprice = ? WHERE bookingid = ?",
                       [len(selectedSeats) * 8.99, bookingid])
        cursor.execute("DELETE FROM bookingdetail WHERE bookingid = ?", (bookingid,))
        for seat in selectedSeats:
            cursor.execute("INSERT INTO bookingdetail (bookingid, seatid) VALUES (?, ?)", [bookingid, seat.split()[0]])
        conn.commit()
    return account()


if __name__ == '__main__':
    app.run(debug=True)
