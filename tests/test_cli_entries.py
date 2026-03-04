"""CLI tests for entry add/list/search/edit/delete/expand commands."""
from unittest.mock import patch

import book_agent.db as db_module
from book_agent.main import cli


def _add_book(runner, title="Valis"):
    runner.invoke(cli, ["book", "add", title, "--author", "Philip K. Dick"])


# ── add quote ─────────────────────────────────────────────────────────────


def test_add_quote(tmp_db, runner):
    _add_book(runner)
    result = runner.invoke(cli, ["add", "quote", "Valis", "--content", "The empire never ended"])
    assert result.exit_code == 0
    assert "Added quote" in result.output

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM entries WHERE content = 'The empire never ended'").fetchone()
    conn.close()
    assert row is not None
    assert row["entry_type"] == "quote"


def test_add_quote_book_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["add", "quote", "Ghost Book", "--content", "Some text"])
    assert "not found" in result.output


def test_add_quote_no_content(tmp_db, runner):
    _add_book(runner)
    result = runner.invoke(cli, ["add", "quote", "Valis"])
    assert "Provide either" in result.output


def test_add_quote_both_content_and_image_fails(tmp_db, runner):
    _add_book(runner)
    result = runner.invoke(cli, ["add", "quote", "Valis", "--content", "text", "--from-image", "/tmp/img.png"])
    assert "Cannot use both" in result.output


# ── add reference (auto-tagging) ──────────────────────────────────────────


def test_add_reference_autotags(tmp_db, runner):
    _add_book(runner)
    with patch("book_agent.ollama_client.generate_tags", return_value="philosophy,gnosticism,theology"):
        result = runner.invoke(cli, ["add", "reference", "Valis", "--content", "Gnostic dualism"])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT tags FROM entries WHERE content = 'Gnostic dualism'").fetchone()
    conn.close()
    assert row["tags"] == "philosophy,gnosticism,theology"


def test_add_reference_ollama_unavailable(tmp_db, runner):
    _add_book(runner)
    with patch("book_agent.ollama_client.generate_tags", return_value=None):
        result = runner.invoke(cli, ["add", "reference", "Valis", "--content", "Heraklitus"])
    assert result.exit_code == 0
    assert "unavailable" in result.output


def test_add_reference_manual_tags_skip_autotag(tmp_db, runner):
    _add_book(runner)
    with patch("book_agent.ollama_client.generate_tags") as mock_tags:
        runner.invoke(cli, ["add", "reference", "Valis",
                            "--content", "Heraklitus", "--tags", "greek,philosophy"])
        mock_tags.assert_not_called()

    conn = db_module.get_connection()
    row = conn.execute("SELECT tags FROM entries").fetchone()
    conn.close()
    assert row["tags"] == "greek,philosophy"


# ── add with --expand ─────────────────────────────────────────────────────


def test_add_reference_expand(tmp_db, runner):
    _add_book(runner)
    with patch("book_agent.ollama_client.generate_tags", return_value=None):
        with patch("book_agent.ollama_client.expand_entry", return_value="Gnosticism is an ancient..."):
            result = runner.invoke(cli, ["add", "reference", "Valis",
                                        "--content", "Gnostic dualism", "--expand"])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT expanded FROM entries").fetchone()
    conn.close()
    assert row["expanded"] == "Gnosticism is an ancient..."


# ── list ───────────────────────────────────────────────────────────────────


def test_list_entries(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "The empire never ended"])
    result = runner.invoke(cli, ["list", "Valis"])
    assert "The empire never ended" in result.output


def test_list_entries_filtered_by_type(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "A quote"])
    with patch("book_agent.ollama_client.generate_tags", return_value=None):
        runner.invoke(cli, ["add", "reference", "Valis", "--content", "A reference"])

    result = runner.invoke(cli, ["list", "Valis", "--type", "quote"])
    assert "A quote" in result.output
    assert "A reference" not in result.output


def test_list_entries_book_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["list", "Nonexistent"])
    assert "not found" in result.output


def test_list_entries_empty(tmp_db, runner):
    _add_book(runner)
    result = runner.invoke(cli, ["list", "Valis"])
    assert "No entries" in result.output


# ── search ─────────────────────────────────────────────────────────────────


def test_search_finds_by_content(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "The empire never ended"])
    result = runner.invoke(cli, ["search", "empire"])
    assert "The empire never ended" in result.output


def test_search_finds_by_context(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis",
                        "--content", "A quote", "--context", "about theophany"])
    result = runner.invoke(cli, ["search", "theophany"])
    assert "A quote" in result.output


def test_search_no_results(tmp_db, runner):
    result = runner.invoke(cli, ["search", "xyznotfound123"])
    assert "No results" in result.output


# ── delete ─────────────────────────────────────────────────────────────────


def test_delete_entry(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "A quote"])

    conn = db_module.get_connection()
    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    conn.close()

    result = runner.invoke(cli, ["delete", str(entry_id)])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    assert row is None


def test_delete_entry_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["delete", "9999"])
    assert "not found" in result.output


# ── edit ───────────────────────────────────────────────────────────────────


def test_edit_entry_content(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "Old content"])

    conn = db_module.get_connection()
    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    conn.close()

    result = runner.invoke(cli, ["edit", str(entry_id), "--content", "New content"])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT content FROM entries WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    assert row["content"] == "New content"


def test_edit_entry_no_options_warns(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "A quote"])

    conn = db_module.get_connection()
    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    conn.close()

    result = runner.invoke(cli, ["edit", str(entry_id)])
    assert "Nothing to update" in result.output


# ── expand ─────────────────────────────────────────────────────────────────


def test_expand_entry(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "Gnostic reference"])

    conn = db_module.get_connection()
    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    conn.close()

    with patch("book_agent.ollama_client.expand_entry", return_value="Gnosticism is..."):
        result = runner.invoke(cli, ["expand", str(entry_id)])
    assert result.exit_code == 0

    conn = db_module.get_connection()
    row = conn.execute("SELECT expanded FROM entries WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    assert row["expanded"] == "Gnosticism is..."


def test_expand_entry_ollama_unavailable(tmp_db, runner):
    _add_book(runner)
    runner.invoke(cli, ["add", "quote", "Valis", "--content", "A reference"])

    conn = db_module.get_connection()
    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    conn.close()

    with patch("book_agent.ollama_client.expand_entry", return_value=None):
        result = runner.invoke(cli, ["expand", str(entry_id)])
    assert "not running" in result.output


def test_expand_entry_not_found(tmp_db, runner):
    result = runner.invoke(cli, ["expand", "9999"])
    assert "not found" in result.output
