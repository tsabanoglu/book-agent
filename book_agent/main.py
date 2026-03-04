import sqlite3
from datetime import datetime

import click

from book_agent.db import init_db, get_connection
from book_agent.display import (
    console,
    show_books,
    show_entries,
    show_entry_detail,
    show_reading_list,
    show_plan_stats,
)
from book_agent.models import Book, Entry, ReadingListItem
from book_agent.ollama_client import expand_entry, extract_text_from_image, generate_tags


@click.group()
def cli():
    """Personal reading companion — track quotes, references, concepts, and notes."""
    init_db()


# ── book subgroup ──────────────────────────────────────────────────────────


@cli.group()
def book():
    """Manage your books."""


@book.command("add")
@click.argument("title")
@click.option("--author", default=None, help="Book author")
@click.option("--format", "fmt", type=click.Choice(["physical", "digital"]), default=None)
@click.option("--read-type", default=None, help="e.g. 'first read' or 'reread'")
@click.option("--started", default=None, help="Start date, e.g. 2026-01-15")
@click.option("--finished", default=None, help="Finish date, e.g. 2026-02-01")
@click.option("--language", default=None, help="e.g. english, turkish, german")
@click.option("--translation", type=click.Choice(["original", "translation"]), default=None)
@click.option("--genre", default=None, help="e.g. science fiction, philosophy, literary fiction")
@click.option("--form", "form_", default=None, help="e.g. novel, poetry, essay, short stories")
@click.option("--pages", type=int, default=None, help="Total number of pages")
def book_add(title, author, fmt, read_type, started, finished, language, translation, genre, form_, pages):
    """Add a new book to your library."""
    started_at = started or datetime.now().strftime("%Y-%m-%d")
    status = "finished" if finished else "reading"
    conn = get_connection()
    conn.execute(
        "INSERT INTO books (title, author, started_at, finished_at, status, format, read_type, language, translation, genre, form, pages) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, author, started_at, finished, status, fmt, read_type, language, translation, genre, form_, pages),
    )
    conn.commit()
    conn.close()
    console.print(f"[green]Added:[/green] {title}")


@book.command("list")
def book_list():
    """List all books."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM books ORDER BY started_at DESC").fetchall()
    conn.close()
    show_books([Book.from_row(r) for r in rows])


@book.command("edit")
@click.argument("title")
@click.option("--author", default=None)
@click.option("--format", "fmt", type=click.Choice(["physical", "digital"]), default=None)
@click.option("--read-type", default=None)
@click.option("--language", default=None)
@click.option("--translation", type=click.Choice(["original", "translation"]), default=None)
@click.option("--started", default=None)
@click.option("--finished", default=None)
@click.option("--genre", default=None)
@click.option("--form", "form_", default=None)
@click.option("--pages", type=int, default=None)
def book_edit(title, author, fmt, read_type, language, translation, started, finished, genre, form_, pages):
    """Edit a book's details. Only provided fields are updated."""
    updates = {}
    if author is not None:
        updates["author"] = author
    if fmt is not None:
        updates["format"] = fmt
    if read_type is not None:
        updates["read_type"] = read_type
    if language is not None:
        updates["language"] = language
    if translation is not None:
        updates["translation"] = translation
    if started is not None:
        updates["started_at"] = started
    if finished is not None:
        updates["finished_at"] = finished
    if genre is not None:
        updates["genre"] = genre
    if form_ is not None:
        updates["form"] = form_
    if pages is not None:
        updates["pages"] = pages

    if not updates:
        console.print("[yellow]Nothing to update — pass at least one option.[/yellow]")
        return

    conn = get_connection()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    cur = conn.execute(
        f"UPDATE books SET {set_clause} WHERE title = ?",
        (*updates.values(), title),
    )
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        console.print(f"[red]Book not found:[/red] {title}")
    else:
        console.print(f"[green]Updated:[/green] {title}")


@book.command("status")
@click.argument("title")
@click.argument("status", type=click.Choice(["reading", "finished", "paused"]))
def book_status(title, status):
    """Update a book's reading status."""
    conn = get_connection()
    finished_at = datetime.now().strftime("%Y-%m-%d") if status == "finished" else None
    cur = conn.execute(
        "UPDATE books SET status = ?, finished_at = COALESCE(?, finished_at) WHERE title = ?",
        (status, finished_at, title),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        console.print(f"[red]Book not found:[/red] {title}")
    else:
        console.print(f"[green]{title}[/green] -> {status}")


# ── add subgroup ───────────────────────────────────────────────────────────


@cli.group("add")
def add_entry():
    """Add a quote, reference, concept, or note to a book."""


def _resolve_content(content: str | None, from_image: str | None) -> str | None:
    """Resolve content from --content or --from-image. Returns text or None on failure."""
    if content and from_image:
        console.print("[red]Cannot use both --content and --from-image.[/red]")
        return None
    if not content and not from_image:
        console.print("[red]Provide either --content or --from-image.[/red]")
        return None

    if content:
        return content

    console.print("[dim]Extracting text from image via Ollama...[/dim]")
    text = extract_text_from_image(from_image)
    if not text:
        console.print("[red]Failed to extract text. Is Ollama running with a vision model?[/red]")
        return None

    console.print(f"\n[bold]Extracted text:[/bold]\n{text}\n")
    choice = click.prompt("Accept? [y]es / [n]o / [e]dit", type=str, default="y").lower()
    if choice.startswith("n"):
        console.print("[yellow]Aborted.[/yellow]")
        return None
    if choice.startswith("e"):
        edited = click.edit(text)
        if edited is None:
            console.print("[yellow]Editor closed without saving — using original text.[/yellow]")
            return text
        return edited.strip()
    return text


def _resolve_book(conn, title: str):
    """Look up a book by title and return its row, or None."""
    return conn.execute("SELECT * FROM books WHERE title = ?", (title,)).fetchone()


def _add_entry(title, entry_type, content, page, context, tags, expand):
    conn = get_connection()
    book_row = _resolve_book(conn, title)
    if not book_row:
        console.print(f"[red]Book not found:[/red] {title}")
        conn.close()
        return

    book = Book.from_row(book_row)

    # Auto-tag references and concepts if no manual tags provided
    if entry_type in ("reference", "concept") and not tags:
        console.print("[dim]Generating tags via Ollama...[/dim]")
        auto_tags = generate_tags(content, context)
        if auto_tags:
            tags = auto_tags
            console.print(f"[dim]Tags:[/dim] {tags}")
        else:
            console.print("[yellow]Ollama unavailable — saved without tags.[/yellow]")

    expanded = None

    if expand:
        console.print("[dim]Expanding via Ollama...[/dim]")
        expanded = expand_entry(content, book.title, book.author, context)
        if expanded is None:
            console.print("[yellow]Ollama unavailable — saved without expansion.[/yellow]")

    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO entries (book_id, entry_type, content, page, context, expanded, tags, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (book.id, entry_type, content, page, context, expanded, tags, now),
    )
    conn.commit()
    conn.close()
    console.print(f"[green]Added {entry_type}[/green] to {title}")

    if expanded:
        console.print(f"\n[bold]Expanded:[/bold]\n{expanded}")


@add_entry.command("quote")
@click.argument("title")
@click.option("--content", default=None, help="The quote text")
@click.option("--from-image", default=None, type=click.Path(exists=True), help="Extract text from a photo")
@click.option("--page", type=int, default=None)
@click.option("--context", default=None, help="Surrounding context or notes")
@click.option("--tags", default=None, help="Comma-separated tags")
def add_quote(title, content, from_image, page, context, tags):
    """Add a quote from a book."""
    resolved = _resolve_content(content, from_image)
    if resolved is None:
        return
    _add_entry(title, "quote", resolved, page, context, tags, expand=False)


@add_entry.command("reference")
@click.argument("title")
@click.option("--content", default=None, help="The reference")
@click.option("--from-image", default=None, type=click.Path(exists=True), help="Extract text from a photo")
@click.option("--page", type=int, default=None)
@click.option("--context", default=None)
@click.option("--tags", default=None)
@click.option("--expand", is_flag=True, help="Expand via Ollama")
def add_reference(title, content, from_image, page, context, tags, expand):
    """Add a reference from a book."""
    resolved = _resolve_content(content, from_image)
    if resolved is None:
        return
    _add_entry(title, "reference", resolved, page, context, tags, expand)


@add_entry.command("concept")
@click.argument("title")
@click.option("--content", default=None, help="The concept")
@click.option("--from-image", default=None, type=click.Path(exists=True), help="Extract text from a photo")
@click.option("--page", type=int, default=None)
@click.option("--context", default=None)
@click.option("--tags", default=None)
@click.option("--expand", is_flag=True, help="Expand via Ollama")
def add_concept(title, content, from_image, page, context, tags, expand):
    """Add a concept from a book."""
    resolved = _resolve_content(content, from_image)
    if resolved is None:
        return
    _add_entry(title, "concept", resolved, page, context, tags, expand)


@add_entry.command("note")
@click.argument("title")
@click.option("--content", default=None, help="Your note")
@click.option("--from-image", default=None, type=click.Path(exists=True), help="Extract text from a photo")
@click.option("--page", type=int, default=None)
@click.option("--context", default=None)
@click.option("--tags", default=None)
def add_note(title, content, from_image, page, context, tags):
    """Add a personal note for a book."""
    resolved = _resolve_content(content, from_image)
    if resolved is None:
        return
    _add_entry(title, "note", resolved, page, context, tags, expand=False)


# ── top-level commands ─────────────────────────────────────────────────────


@cli.command("list")
@click.argument("title")
@click.option("--type", "entry_type", default=None, help="Filter by type: quote/reference/concept/note")
def list_entries(title, entry_type):
    """List entries for a book."""
    conn = get_connection()
    book_row = _resolve_book(conn, title)
    if not book_row:
        console.print(f"[red]Book not found:[/red] {title}")
        conn.close()
        return

    query = "SELECT * FROM entries WHERE book_id = ?"
    params: list = [book_row["id"]]
    if entry_type:
        query += " AND entry_type = ?"
        params.append(entry_type)
    query += " ORDER BY created_at"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    show_entries([Entry.from_row(r) for r in rows], book_title=title)


@cli.command("search")
@click.argument("query")
def search(query):
    """Search entries by content, context, or expanded text."""
    conn = get_connection()
    pattern = f"%{query}%"
    rows = conn.execute(
        "SELECT e.*, b.title as book_title FROM entries e "
        "JOIN books b ON e.book_id = b.id "
        "WHERE e.content LIKE ? OR e.context LIKE ? OR e.expanded LIKE ? OR e.tags LIKE ? "
        "ORDER BY e.created_at",
        (pattern, pattern, pattern, pattern),
    ).fetchall()
    conn.close()

    if not rows:
        console.print(f"[dim]No results for:[/dim] {query}")
        return

    for row in rows:
        entry = Entry.from_row(row)
        show_entry_detail(entry, book_title=row["book_title"])


@cli.command("expand")
@click.argument("entry_id", type=int)
def expand(entry_id):
    """Expand an existing entry via Ollama."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry not found:[/red] #{entry_id}")
        conn.close()
        return

    entry = Entry.from_row(row)
    book_row = conn.execute("SELECT * FROM books WHERE id = ?", (entry.book_id,)).fetchone()
    book = Book.from_row(book_row)

    console.print("[dim]Expanding via Ollama...[/dim]")
    result = expand_entry(entry.content, book.title, book.author, entry.context)

    if result is None:
        console.print("[red]Ollama is not running or not reachable.[/red]")
        conn.close()
        return

    conn.execute("UPDATE entries SET expanded = ? WHERE id = ?", (result, entry_id))
    conn.commit()
    conn.close()

    entry.expanded = result
    show_entry_detail(entry, book_title=book.title)


@cli.command("delete")
@click.argument("entry_id", type=int)
def delete(entry_id):
    """Delete an entry by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry not found:[/red] #{entry_id}")
        conn.close()
        return

    entry = Entry.from_row(row)
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    console.print(f"[green]Deleted[/green] {entry.entry_type} #{entry_id}")


@cli.command("edit")
@click.argument("entry_id", type=int)
@click.option("--content", default=None, help="New content")
@click.option("--page", type=int, default=None, help="New page number")
@click.option("--context", default=None, help="New context")
@click.option("--tags", default=None, help="New tags")
def edit(entry_id, content, page, context, tags):
    """Edit an entry by ID. Only provided fields are updated."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry not found:[/red] #{entry_id}")
        conn.close()
        return

    updates = {}
    if content is not None:
        updates["content"] = content
    if page is not None:
        updates["page"] = page
    if context is not None:
        updates["context"] = context
    if tags is not None:
        updates["tags"] = tags

    if not updates:
        console.print("[yellow]Nothing to update — pass at least one option.[/yellow]")
        conn.close()
        return

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE entries SET {set_clause} WHERE id = ?",
        (*updates.values(), entry_id),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    entry = Entry.from_row(updated)
    book_row = conn.execute("SELECT * FROM books WHERE id = ?", (entry.book_id,)).fetchone()
    conn.close()

    console.print(f"[green]Updated[/green] #{entry_id}")
    show_entry_detail(entry, book_title=book_row["title"])


@cli.command("retag")
@click.option("--all", "retag_all", is_flag=True, help="Re-tag entries that already have tags too")
def retag(retag_all):
    """Auto-tag all references and concepts via Ollama."""
    conn = get_connection()
    if retag_all:
        rows = conn.execute(
            "SELECT e.*, b.title as book_title FROM entries e "
            "JOIN books b ON e.book_id = b.id "
            "WHERE e.entry_type IN ('reference', 'concept') "
            "ORDER BY e.id"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT e.*, b.title as book_title FROM entries e "
            "JOIN books b ON e.book_id = b.id "
            "WHERE e.entry_type IN ('reference', 'concept') AND (e.tags IS NULL OR e.tags = '') "
            "ORDER BY e.id"
        ).fetchall()

    if not rows:
        console.print("[dim]No entries to tag.[/dim]")
        conn.close()
        return

    console.print(f"[bold]Tagging {len(rows)} entries...[/bold]\n")
    tagged = 0
    for row in rows:
        entry = Entry.from_row(row)
        console.print(f"  #{entry.id} [{entry.entry_type}] {entry.content}", end="")
        tags = generate_tags(entry.content, entry.context)
        if tags:
            conn.execute("UPDATE entries SET tags = ? WHERE id = ?", (tags, entry.id))
            console.print(f" -> [green]{tags}[/green]")
            tagged += 1
        else:
            console.print(f" -> [yellow]failed[/yellow]")

    conn.commit()
    conn.close()
    console.print(f"\n[bold green]Tagged {tagged}/{len(rows)} entries.[/bold green]")


# ── plan subgroup ──────────────────────────────────────────────────────────


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def _next_month(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    mon += 1
    if mon > 12:
        mon = 1
        year += 1
    return f"{year:04d}-{mon:02d}"


def _validate_month(ctx, param, value):
    if value is None:
        return None
    import re
    if not re.match(r"^\d{4}-\d{2}$", value):
        raise click.BadParameter("Month must be in YYYY-MM format.")
    m = int(value[5:7])
    if m < 1 or m > 12:
        raise click.BadParameter("Month must be 01–12.")
    return value


def _auto_link(conn, title: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM books WHERE LOWER(title) = LOWER(?)", (title,)
    ).fetchone()
    return row["id"] if row else None


def _refresh_links(conn, month: str):
    items = conn.execute(
        "SELECT id, title FROM reading_list WHERE month = ?", (month,)
    ).fetchall()
    for item in items:
        book_id = _auto_link(conn, item["title"])
        conn.execute(
            "UPDATE reading_list SET book_id = ? WHERE id = ?",
            (book_id, item["id"]),
        )
    conn.commit()


def _compute_month_stats(conn, month: str) -> dict:
    _refresh_links(conn, month)
    rows = conn.execute(
        "SELECT * FROM reading_list WHERE month = ?", (month,)
    ).fetchall()
    items = [ReadingListItem.from_row(r) for r in rows]

    total = len(items)
    finished = sum(1 for i in items if i.status == "finished")
    carried = sum(1 for i in items if i.status == "carried")

    # unplanned reads: books finished that month (by finished_at) not on the plan
    plan_titles = {i.title.lower() for i in items}
    unplanned_rows = conn.execute(
        "SELECT title FROM books WHERE strftime('%Y-%m', finished_at) = ? AND status = 'finished'",
        (month,),
    ).fetchall()
    unplanned = sum(1 for r in unplanned_rows if r["title"].lower() not in plan_titles)

    # genre balance from linked books
    genres: dict[str, int] = {}
    linked_ids = [i.book_id for i in items if i.book_id]
    for bid in linked_ids:
        brow = conn.execute("SELECT genre FROM books WHERE id = ?", (bid,)).fetchone()
        if brow and brow["genre"]:
            g = brow["genre"]
            genres[g] = genres.get(g, 0) + 1

    streak = _compute_streak(conn, month)

    return {
        "total": total,
        "finished": finished,
        "carried": carried,
        "unplanned": unplanned,
        "streak": streak,
        "genres": genres,
    }


def _compute_all_time_stats(conn) -> dict:
    months = conn.execute(
        "SELECT DISTINCT month FROM reading_list ORDER BY month"
    ).fetchall()
    months = [r["month"] for r in months]
    if not months:
        return {"total": 0, "finished": 0, "carried": 0, "unplanned": 0, "streak": 0, "genres": {}}

    total = finished = carried = unplanned = 0
    genres: dict[str, int] = {}
    for m in months:
        s = _compute_month_stats(conn, m)
        total += s["total"]
        finished += s["finished"]
        carried += s["carried"]
        unplanned += s["unplanned"]
        for g, c in s["genres"].items():
            genres[g] = genres.get(g, 0) + c

    streak = _compute_streak(conn, _current_month())
    return {
        "total": total,
        "finished": finished,
        "carried": carried,
        "unplanned": unplanned,
        "streak": streak,
        "genres": genres,
    }


def _compute_streak(conn, from_month: str) -> int:
    streak = 0
    month = from_month
    while True:
        rows = conn.execute(
            "SELECT * FROM reading_list WHERE month = ?", (month,)
        ).fetchall()
        if not rows:
            break
        total = len(rows)
        finished = sum(1 for r in rows if r["status"] == "finished")
        if total > 0 and (finished / total) >= 0.5:
            streak += 1
        else:
            break
        # go to previous month
        year, mon = int(month[:4]), int(month[5:7])
        mon -= 1
        if mon < 1:
            mon = 12
            year -= 1
        month = f"{year:04d}-{mon:02d}"
    return streak


@cli.group()
def plan():
    """Monthly reading plan & tracking."""


@plan.command("add")
@click.argument("titles", nargs=-1, required=True)
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
def plan_add(titles, month):
    """Add one or more books to your monthly reading plan."""
    month = month or _current_month()
    conn = get_connection()
    now = datetime.now().isoformat()
    for title in titles:
        book_id = _auto_link(conn, title)
        try:
            conn.execute(
                "INSERT INTO reading_list (month, title, status, book_id, created_at) VALUES (?, ?, 'planned', ?, ?)",
                (month, title, book_id, now),
            )
            conn.commit()
            linked = " (linked)" if book_id else ""
            console.print(f"[green]Added to {month} plan:[/green] {title}{linked}")
        except sqlite3.IntegrityError:
            console.print(f"[yellow]'{title}' is already on the {month} plan.[/yellow]")
    conn.close()


@plan.command("list")
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
def plan_list(month):
    """Show your reading plan for a month."""
    month = month or _current_month()
    conn = get_connection()
    _refresh_links(conn, month)
    rows = conn.execute(
        "SELECT * FROM reading_list WHERE month = ? ORDER BY created_at", (month,)
    ).fetchall()
    conn.close()
    items = [ReadingListItem.from_row(r) for r in rows]
    show_reading_list(items, month)


@plan.command("status")
@click.argument("title")
@click.argument("new_status", type=click.Choice(["planned", "reading", "finished", "dropped", "carried"]))
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
def plan_status(title, new_status, month):
    """Update the status of a book on your plan."""
    month = month or _current_month()
    conn = get_connection()
    cur = conn.execute(
        "UPDATE reading_list SET status = ? WHERE month = ? AND LOWER(title) = LOWER(?)",
        (new_status, month, title),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        console.print(f"[red]'{title}' not found on the {month} plan.[/red]")
    else:
        console.print(f"[green]{title}[/green] -> {new_status}")


@plan.command("remove")
@click.argument("title")
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
def plan_remove(title, month):
    """Remove a book from your plan."""
    month = month or _current_month()
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM reading_list WHERE month = ? AND LOWER(title) = LOWER(?)",
        (month, title),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        console.print(f"[red]'{title}' not found on the {month} plan.[/red]")
    else:
        console.print(f"[green]Removed:[/green] {title} from {month}")


@plan.command("carry")
@click.argument("title")
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
def plan_carry(title, month):
    """Carry a book forward to the next month."""
    month = month or _current_month()
    next_m = _next_month(month)
    conn = get_connection()

    # mark as carried in current month
    cur = conn.execute(
        "UPDATE reading_list SET status = 'carried' WHERE month = ? AND LOWER(title) = LOWER(?)",
        (month, title),
    )
    if cur.rowcount == 0:
        console.print(f"[red]'{title}' not found on the {month} plan.[/red]")
        conn.close()
        return

    # get the original title casing
    row = conn.execute(
        "SELECT title, book_id FROM reading_list WHERE month = ? AND LOWER(title) = LOWER(?)",
        (month, title),
    ).fetchone()
    original_title = row["title"]
    book_id = row["book_id"]

    # insert into next month
    now = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT INTO reading_list (month, title, status, book_id, created_at) VALUES (?, ?, 'planned', ?, ?)",
            (next_m, original_title, book_id, now),
        )
    except sqlite3.IntegrityError:
        console.print(f"[yellow]'{original_title}' is already on the {next_m} plan.[/yellow]")

    conn.commit()
    conn.close()
    console.print(f"[green]Carried:[/green] {original_title} -> {next_m}")


@plan.command("stats")
@click.option("--month", default=None, callback=_validate_month, help="YYYY-MM (default: current month)")
@click.option("--all", "all_time", is_flag=True, help="Show all-time stats")
def plan_stats(month, all_time):
    """Show reading plan metrics."""
    conn = get_connection()
    if all_time:
        stats = _compute_all_time_stats(conn)
        conn.close()
        show_plan_stats(stats, None)
    else:
        month = month or _current_month()
        stats = _compute_month_stats(conn, month)
        conn.close()
        show_plan_stats(stats, month)


if __name__ == "__main__":
    cli()
