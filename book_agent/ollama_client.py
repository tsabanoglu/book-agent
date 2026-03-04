import base64
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3"
VISION_MODEL = "minicpm-v"


def extract_text_from_image(image_path: str) -> str | None:
    """Use Ollama vision model to extract text from a photo of a book page."""
    path = Path(image_path)
    if not path.exists():
        return None

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

    prompt = (
        "Extract all the text from this image of a book page. "
        "Return ONLY the extracted text, nothing else. "
        "Clean up any line-break hyphenation (rejoin hyphenated words). "
        "Preserve paragraph breaks but remove artificial line breaks within paragraphs."
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        return text or None
    except requests.ConnectionError:
        return None
    except requests.RequestException:
        return None


def generate_tags(content: str, context: str | None = None) -> str | None:
    """Ask Ollama to generate 2-4 comma-separated tags for a reference or concept."""
    context_part = f"\nContext: \"{context}\"" if context else ""
    prompt = (
        f"Generate exactly 3 tags for this reference or concept:\n"
        f"\"{content}\"{context_part}\n\n"
        "Rules:\n"
        "- Each tag must be 1-2 words maximum\n"
        "- Use broad, reusable categories (e.g. poetry, philosophy, theology, myth, science)\n"
        "- Include the source type (e.g. poem, novel, treatise, essay, painting)\n"
        "- Never concatenate words without spaces\n\n"
        "Examples:\n"
        "Reference: \"Dante's Inferno\" -> dante, epic poem, theology\n"
        "Reference: \"Freud's concept of the uncanny\" -> freud, psychoanalysis, essay\n"
        "Reference: \"Wordsworth's Ode, Intimations of Immortality\" -> wordsworth, poem, romanticism\n\n"
        "Return ONLY 3 comma-separated lowercase tags, nothing else."
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        # Clean up: lowercase, strip whitespace, remove empty, cap at 3
        cleaned = [t.strip().lower() for t in raw.split(",") if t.strip()]
        tags = ",".join(cleaned[:3])
        return tags or None
    except requests.ConnectionError:
        return None
    except requests.RequestException:
        return None


def expand_entry(content: str, book_title: str, author: str | None, context: str | None = None) -> str | None:
    """Ask Ollama to expand a brief reference or concept with richer context."""
    author_part = f" by {author}" if author else ""
    context_part = f"\nReader's note: \"{context}\"" if context else ""
    prompt = (
        f"While reading \"{book_title}\"{author_part}, the reader noted this reference:\n"
        f"\"{content}\"{context_part}\n\n"
        "Explain what this reference is on its own — the person, work, idea, or concept — "
        "independent of the book. Do NOT speculate about how it connects to the book or "
        "its characters. Just explain what the reference itself is. "
        "Be factual and specific. 2-3 sentences, no preamble."
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.ConnectionError:
        return None
    except requests.RequestException:
        return None
