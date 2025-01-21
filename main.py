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
        if "email" in session:
            cursor.execute("SELECT username FROM user WHERE email = ?", (session["email"],))
            name = cursor.fetchone()[0]
        else:
            name = ""
    return render_template("index.html", items=results, message=name)


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
        print(account)
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


@app.route("/showing/<int:showing_id>")
def booking(showing_id):
    return render_template("showing.html", showing=showing_id)


if __name__ == '__main__':
    app.run(debug=True)
