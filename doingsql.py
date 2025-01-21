import sqlite3

with sqlite3.connect('CinemaDatabase.db') as conn:
    cursor = conn.cursor()
    cursor.execute('''
    CREATE UNIQUE INDEX idx_unique_email ON user(email);
    ''')

    conn.commit()
