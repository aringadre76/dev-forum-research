from __future__ import annotations

import html
import re
from collections import Counter

import bleach

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-.]{1,}", re.IGNORECASE)
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "being",
    "broken",
    "during",
    "from",
    "have",
    "into",
    "just",
    "more",
    "need",
    "needs",
    "still",
    "than",
    "that",
    "their",
    "there",
    "this",
    "thread",
    "with",
    "without",
    "workaround",
}


def sanitize_html(value: str | None) -> str:
    if not value:
        return ""
    cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    ]


def top_ngrams(texts: list[str], n: int = 2, limit: int = 20) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        tokens = tokenize(text)
        seen = {
            " ".join(tokens[index : index + n])
            for index in range(0, max(0, len(tokens) - n + 1))
        }
        counter.update(seen)
    return counter.most_common(limit)


def excerpt(text: str, max_length: int = 260) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."
