"""Unit tests for Book, Entry, and ReadingListItem models."""
import sqlite3
from datetime import datetime

from book_agent.models import Book, Entry, ReadingListItem


def _make_row(data: dict):
    """Build a sqlite3.Row from a plain dict."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cols = list(data.keys())
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(f"CREATE TABLE t ({col_defs})")
    conn.execute(f"INSERT INTO t VALUES ({placeholders})", list(data.values()))
    return conn.execute("SELECT * FROM t").fetchone()


# ── Entry.tags_list ────────────────────────────────────────────────────────


def test_tags_list_none():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None, tags=None,
              created_at="2026-01-01T00:00:00")
    assert e.tags_list == []


def test_tags_list_empty_string():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None, tags="",
              created_at="2026-01-01T00:00:00")
    assert e.tags_list == []


def test_tags_list_single():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None, tags="philosophy",
              created_at="2026-01-01T00:00:00")
    assert e.tags_list == ["philosophy"]


def test_tags_list_multiple():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None,
              tags="philosophy,gnosticism,theology",
              created_at="2026-01-01T00:00:00")
    assert e.tags_list == ["philosophy", "gnosticism", "theology"]


def test_tags_list_strips_whitespace():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None,
              tags=" philosophy , theology ",
              created_at="2026-01-01T00:00:00")
    assert e.tags_list == ["philosophy", "theology"]


# ── Entry.timestamp ────────────────────────────────────────────────────────


def test_timestamp_parses_isoformat():
    e = Entry(id=1, book_id=1, entry_type="quote", content="x",
              page=None, context=None, expanded=None, tags=None,
              created_at="2026-03-01T14:30:00")
    assert e.timestamp == datetime(2026, 3, 1, 14, 30, 0)


# ── Book.from_row ──────────────────────────────────────────────────────────


def test_book_from_row():
    row = _make_row({
        "id": "1", "title": "Valis", "author": "Philip K. Dick",
        "started_at": "2026-01-01", "finished_at": None,
        "status": "reading", "format": "physical", "read_type": "first read",
        "language": "english", "translation": "original",
        "genre": "science fiction", "form": "novel", "pages": "300",
    })
    book = Book.from_row(row)
    assert book.title == "Valis"
    assert book.author == "Philip K. Dick"
    assert book.status == "reading"


# ── Entry.from_row ─────────────────────────────────────────────────────────


def test_entry_from_row():
    row = _make_row({
        "id": "5", "book_id": "1", "entry_type": "quote",
        "content": "The empire never ended", "page": "47",
        "context": "opening line", "expanded": None,
        "tags": "philosophy,gnosticism", "created_at": "2026-01-01T10:00:00",
    })
    entry = Entry.from_row(row)
    assert entry.content == "The empire never ended"
    assert entry.entry_type == "quote"
    assert entry.tags == "philosophy,gnosticism"


# ── ReadingListItem.from_row ───────────────────────────────────────────────


def test_reading_list_item_from_row():
    row = _make_row({
        "id": "1", "month": "2026-03", "title": "Valis",
        "status": "planned", "book_id": None, "created_at": "2026-03-01T00:00:00",
    })
    item = ReadingListItem.from_row(row)
    assert item.month == "2026-03"
    assert item.title == "Valis"
    assert item.status == "planned"
