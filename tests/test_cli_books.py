"""CLI tests for the `book` subgroup."""
import book_agent.db as db_module
from book_agent.main import cli


def test_book_add(tmp_db, runner):
    result = runner.invoke(cli, ["book", "add", "Valis", "--author", "Philip K. Dick"])
    assert result.exit_code == 0
    assert "Valis" in result.output

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM books WHERE title = 'Valis'").fetchone()
    conn.close()
    assert row is not None
    assert row["author"] == "Philip K. Dick"
    assert row["status"] == "reading"


def test_book_add_with_finished_sets_status(tmp_db, runner):
    result = runner.invoke(cli, ["book", "add", "Valis", "--finished", "2026-02-01"])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT status, finished_at FROM books WHERE title = 'Valis'").fetchone()
    conn.close()
    assert row["status"] == "finished"
    assert row["finished_at"] == "2026-02-01"


def test_book_list_empty(tmp_db, runner):
    result = runner.invoke(cli, ["book", "list"])
    assert result.exit_code == 0
    assert "No books" in result.output


def test_book_list_shows_books(tmp_db, runner):
    runner.invoke(cli, ["book", "add", "Valis"])
    runner.invoke(cli, ["book", "add", "The Master and Margarita"])
    result = runner.invoke(cli, ["book", "list"])
    assert "Valis" in result.output
    assert "The Master and Margarita" in result.output


def test_book_status_update(tmp_db, runner):
    runner.invoke(cli, ["book", "add", "Valis"])
    result = runner.invoke(cli, ["book", "status", "Valis", "finished"])
    assert result.exit_code == 0
    assert "finished" in result.output

    conn = db_module.get_connection()
    row = conn.execute("SELECT status FROM books WHERE title = 'Valis'").fetchone()
    conn.close()
    assert row["status"] == "finished"


def test_book_status_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["book", "status", "Nonexistent", "reading"])
    assert result.exit_code == 0
    assert "not found" in result.output


def test_book_edit_updates_field(tmp_db, runner):
    runner.invoke(cli, ["book", "add", "Valis"])
    result = runner.invoke(cli, ["book", "edit", "Valis", "--genre", "science fiction", "--pages", "227"])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT genre, pages FROM books WHERE title = 'Valis'").fetchone()
    conn.close()
    assert row["genre"] == "science fiction"
    assert row["pages"] == 227


def test_book_edit_no_options_warns(tmp_db, runner):
    runner.invoke(cli, ["book", "add", "Valis"])
    result = runner.invoke(cli, ["book", "edit", "Valis"])
    assert "Nothing to update" in result.output


def test_book_edit_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["book", "edit", "Nonexistent", "--genre", "fiction"])
    assert "not found" in result.output.lower() or result.exit_code == 0
