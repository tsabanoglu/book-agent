from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from book_agent.models import Book, Entry, ReadingListItem

console = Console()


def _fmt_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(value.split("T")[0])
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return value


def show_books(books: list[Book]):
    if not books:
        console.print("[dim]No books found.[/dim]")
        return

    table = Table(title="Books")
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Author")
    table.add_column("Status")
    table.add_column("Format")
    table.add_column("Read Type")
    table.add_column("Language")
    table.add_column("Translation")
    table.add_column("Genre")
    table.add_column("Form")
    table.add_column("Pages", justify="right")
    table.add_column("Started")
    table.add_column("Finished")

    for b in books:
        status_style = {
            "reading": "green",
            "finished": "blue",
            "paused": "yellow",
        }.get(b.status, "white")

        table.add_row(
            str(b.id),
            b.title,
            b.author or "",
            f"[{status_style}]{b.status}[/{status_style}]",
            b.format or "",
            b.read_type or "",
            b.language or "",
            b.translation or "",
            b.genre or "",
            b.form or "",
            str(b.pages) if b.pages else "",
            _fmt_date(b.started_at),
            _fmt_date(b.finished_at),
        )

    console.print(table)


def show_entries(entries: list[Entry], book_title: str | None = None):
    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return

    title = f"Entries for {book_title}" if book_title else "Entries"
    table = Table(title=title)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Type")
    table.add_column("Content", max_width=50)
    table.add_column("Page", justify="right")
    table.add_column("Tags", style="dim")
    table.add_column("Created", style="dim")

    type_styles = {
        "quote": "italic yellow",
        "reference": "cyan",
        "concept": "magenta",
        "note": "green",
    }

    for e in entries:
        style = type_styles.get(e.entry_type, "white")
        table.add_row(
            str(e.id),
            f"[{style}]{e.entry_type}[/{style}]",
            e.content[:50] + ("..." if len(e.content) > 50 else ""),
            str(e.page) if e.page else "",
            e.tags or "",
            e.created_at,
        )

    console.print(table)


def show_entry_detail(entry: Entry, book_title: str | None = None):
    header = f"[bold]{entry.entry_type.upper()}[/bold] #{entry.id}"
    if book_title:
        header += f"  [dim]({book_title})[/dim]"

    lines = []
    lines.append(f"[bold]Content:[/bold] {entry.content}")
    if entry.page:
        lines.append(f"[bold]Page:[/bold] {entry.page}")
    if entry.context:
        lines.append(f"[bold]Context:[/bold] {entry.context}")
    if entry.tags:
        lines.append(f"[bold]Tags:[/bold] {entry.tags}")
    if entry.expanded:
        lines.append("")
        lines.append(f"[bold]Expanded:[/bold]\n{entry.expanded}")
    lines.append(f"\n[dim]{entry.created_at}[/dim]")

    console.print(Panel("\n".join(lines), title=header))


def show_reading_list(items: list[ReadingListItem], month: str):
    if not items:
        console.print(f"[dim]No reading plan for {month}.[/dim]")
        return

    table = Table(title=f"Reading Plan — {month}")
    table.add_column("Title", style="bold")
    table.add_column("Status")
    table.add_column("Linked", justify="center")

    status_styles = {
        "planned": "white",
        "reading": "green",
        "finished": "blue",
        "dropped": "red",
        "carried": "yellow",
    }

    for item in items:
        style = status_styles.get(item.status, "white")
        linked = "✓" if item.book_id else ""
        table.add_row(
            item.title,
            f"[{style}]{item.status}[/{style}]",
            linked,
        )

    console.print(table)


def show_plan_stats(stats: dict, month: str | None):
    title = f"Plan Stats — {month}" if month else "Plan Stats — All Time"
    lines = []

    total = stats.get("total", 0)
    finished = stats.get("finished", 0)
    rate = (finished / total * 100) if total > 0 else 0
    lines.append(f"[bold]Completion rate:[/bold] {finished}/{total} ({rate:.0f}%)")

    carry_overs = stats.get("carried", 0)
    lines.append(f"[bold]Carry-overs:[/bold] {carry_overs}")

    unplanned = stats.get("unplanned", 0)
    lines.append(f"[bold]Unplanned reads:[/bold] {unplanned}")

    streak = stats.get("streak", 0)
    lines.append(f"[bold]Streak:[/bold] {streak} month{'s' if streak != 1 else ''} (≥50% completion)")

    genres = stats.get("genres", {})
    if genres:
        genre_parts = [f"{g}: {c}" for g, c in sorted(genres.items(), key=lambda x: -x[1])]
        lines.append(f"[bold]Genre balance:[/bold] {', '.join(genre_parts)}")
    else:
        lines.append(f"[bold]Genre balance:[/bold] [dim]no linked books with genres[/dim]")

    console.print(Panel("\n".join(lines), title=title))
