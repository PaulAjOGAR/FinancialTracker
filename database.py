import sqlite3


def get_connection():
    return sqlite3.connect("finance_tracker.db")


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        t_type TEXT NOT NULL,
        category TEXT,
        date TEXT,
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        t_type TEXT,
        amount REAL,
        month INTEGER,
        year INTEGER,
        description TEXT
    )
    """)
    conn.commit()
    conn.close()
