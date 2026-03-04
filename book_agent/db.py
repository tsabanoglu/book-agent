import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".book-agent"
DB_PATH = DB_DIR / "books.db"


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'reading',
            format TEXT,
            read_type TEXT,
            language TEXT,
            translation TEXT,
            genre TEXT,
            form TEXT,
            pages INTEGER
        );

        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id),
            entry_type TEXT NOT NULL,
            content TEXT NOT NULL,
            page INTEGER,
            context TEXT,
            expanded TEXT,
            tags TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reading_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            book_id INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(month, title)
        );
    """)
    # migrate: add language column if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(books)").fetchall()]
    if "language" not in cols:
        conn.execute("ALTER TABLE books ADD COLUMN language TEXT")
    if "translation" not in cols:
        conn.execute("ALTER TABLE books ADD COLUMN translation TEXT")
    if "genre" not in cols:
        conn.execute("ALTER TABLE books ADD COLUMN genre TEXT")
    if "form" not in cols:
        conn.execute("ALTER TABLE books ADD COLUMN form TEXT")
    if "pages" not in cols:
        conn.execute("ALTER TABLE books ADD COLUMN pages INTEGER")
    conn.close()
