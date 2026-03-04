import pytest
from click.testing import CliRunner

import book_agent.db as db_module
from book_agent.db import init_db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Redirect the SQLite DB to a temp directory so tests never touch ~/.book-agent."""
    monkeypatch.setattr(db_module, "DB_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "books.db")
    init_db()


@pytest.fixture
def runner():
    return CliRunner()
