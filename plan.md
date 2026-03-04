# Book Agent - Project Plan

A personal reading companion that goes beyond metadata. Track references, save quotes, store concepts, and build a mind map of your readings over time.

## Core Ideas

- Manual entry first, automation later
- Every entry gets auto-timestamped (track reading habits)
- Ollama for AI features (expanding concepts, finding context)
- SQLite as the persistent store
- Start simple, grow into a knowledge graph / mind map

## Database Schema

### books
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| title | TEXT | required |
| author | TEXT | |
| started_at | TIMESTAMP | auto |
| finished_at | TIMESTAMP | nullable |
| status | TEXT | reading / finished / paused |
| format | TEXT | physical / digital |
| read_type | TEXT | first read / reread |

### entries
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| book_id | INTEGER | FK -> books |
| entry_type | TEXT | quote / reference / concept / note |
| content | TEXT | the actual text or description |
| page | TEXT | page number or location (text to support both physical and digital) |
| context | TEXT | surrounding context, why it matters |
| expanded | TEXT | Ollama-generated expansion (nullable) |
| tags | TEXT | comma-separated for now, normalize later |
| created_at | TIMESTAMP | auto |

## CLI Commands

### Phase 1 - Core (MVP)
```
book add "Valis" --author "Philip K. Dick" --format physical
book list
book status "Valis" reading

entry add quote "Valis" --content "The empire never ended" --page 47
entry add reference "Valis" --content "Jung's collective unconscious" --page 23 --context "Dick connects his experiences to..."
entry add concept "Valis" --content "Gnostic dualism" --page 85
entry list "Valis"
entry list "Valis" --type reference
entry search "Jung"
```

### Phase 2 - Ollama Integration
```
entry expand 5                  # expand entry #5 using Ollama
entry add reference "Valis" --content "Heraklitus's concept of flux" --expand
                                # auto-expand on add
book summary "Valis"            # AI-generated summary of all entries for a book
```

### Phase 3 - Reading Habits & Insights
```
book stats                      # reading pace, entries per day, active hours
book timeline "Valis"           # chronological view of entries
```

### Phase 4 - Mind Map / Knowledge Graph
- Cross-book concept linking (e.g. Jung appears in Valis and another book)
- Tag-based clustering
- Export to a visual format

## Tech Stack

- **Python 3.13** (uv managed)
- **SQLite** via built-in `sqlite3`
- **Ollama** (already installed) - local LLM for expansions
- **Click** or **argparse** for CLI (decide during implementation)
- **Rich** for terminal output (nice tables, formatting)

## Project Structure

```
book-agent/
  main.py          # CLI entrypoint
  db.py            # database setup, migrations, queries
  models.py        # data classes for Book, Entry
  ollama_client.py # Ollama integration
  display.py       # terminal formatting / output
  books.db         # SQLite database (gitignored)
```

## TODO

- [ ] Improve tagging logic — current prompt produces inconsistent/noisy results. Consider few-shot examples in the prompt, post-processing to filter junk tags, or a curated tag vocabulary.

## Open Questions

- CLI framework: Click vs argparse vs just a REPL-style interface?
- Do we want a REPL mode too? (e.g. `book-agent` drops you into a prompt)
- Export formats: JSON, markdown, or both?
- Ollama model choice: which model to use for expansions?
