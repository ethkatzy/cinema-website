# cinema-website
## Description
* On the website, users can search for upcoming films that are playing. The film page will incluce a poster, the film rating, a synopsis, the runtime, cast and crew and genre, as well as the times the film is playing.
* The user can create an account and log in to the website.
* The user can create, edit and delete bookings.
* The user can see films that have been added to the website.
* The user can search for films by their title, as well as keywords based on other information on the film page.
* The user page shows all past and future bookings the user has.
* The user can select one or more classifications for the film.
* The user can make a booking for a film, including the number of seats, and picking which seat they want to sit in.

## How to run
Clone the repository, and make sure you have all the necessary libraries installed by running the following commands:
```
pip install flask
pip install sqlite3
```

### Re-installing the database:
If you wish to create a new database from the schema, you can run the following command `sqlite CinemaDatabase.db < schema.sql`.

### Launching the website:
Do one of the following:
* Run `main.py` from an IDE
* Run the command `flask run`
* Execute `main.py` from the command line

Then in a browser open `127.0.0.1:5000`.