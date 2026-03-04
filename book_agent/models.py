from dataclasses import dataclass
from datetime import datetime


@dataclass
class Book:
    id: int | None
    title: str
    author: str | None
    started_at: str | None
    finished_at: str | None
    status: str
    format: str | None
    read_type: str | None
    language: str | None
    translation: str | None
    genre: str | None
    form: str | None
    pages: int | None

    @classmethod
    def from_row(cls, row) -> "Book":
        return cls(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            format=row["format"],
            read_type=row["read_type"],
            language=row["language"],
            translation=row["translation"],
            genre=row["genre"],
            form=row["form"],
            pages=row["pages"],
        )


@dataclass
class Entry:
    id: int | None
    book_id: int
    entry_type: str
    content: str
    page: int | None
    context: str | None
    expanded: str | None
    tags: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Entry":
        return cls(
            id=row["id"],
            book_id=row["book_id"],
            entry_type=row["entry_type"],
            content=row["content"],
            page=row["page"],
            context=row["context"],
            expanded=row["expanded"],
            tags=row["tags"],
            created_at=row["created_at"],
        )

    @property
    def tags_list(self) -> list[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",")]

    @property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.created_at)


@dataclass
class ReadingListItem:
    id: int | None
    month: str
    title: str
    status: str
    book_id: int | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ReadingListItem":
        return cls(
            id=row["id"],
            month=row["month"],
            title=row["title"],
            status=row["status"],
            book_id=row["book_id"],
            created_at=row["created_at"],
        )
