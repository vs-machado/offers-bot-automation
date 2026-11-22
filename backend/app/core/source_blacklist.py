import re
import unicodedata
from typing import TypedDict

from backend.app.core.source_groups import approved_source

SOURCE_BLACKLISTS = "source_blacklists"
MAX_TERMS = 50
MAX_TERM_LENGTH = 80


class SourceBlacklist(TypedDict):
    source: str
    terms: list[str]


def _search_words(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", unaccented))


def validate_source_blacklists(
    raw: object, catalog: list[str] | None
) -> list[SourceBlacklist]:
    """Validate per-source terms and store only nonempty lists under canonical URLs."""
    if not isinstance(raw, list):
        raise ValueError("Informe uma lista de termos por grupo de origem.")
    result: dict[str, list[str]] = {}
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
            raise ValueError("Selecione o grupo de origem da lista de bloqueio.")
        url = approved_source(entry["source"], catalog)
        terms = entry.get("terms")
        if not isinstance(terms, list) or len(terms) > MAX_TERMS:
            raise ValueError(f"Use até {MAX_TERMS} termos por grupo de origem.")
        cleaned = result.setdefault(url, [])
        seen = {_search_words(term) for term in cleaned}
        for term in terms:
            if not isinstance(term, str) or len(term) > MAX_TERM_LENGTH:
                raise ValueError(f"Use termos de até {MAX_TERM_LENGTH} caracteres.")
            display_term = " ".join(term.split())
            if not display_term:
                continue
            key = _search_words(display_term)
            if not key:
                raise ValueError(
                    "Cada termo deve conter pelo menos uma letra ou número."
                )
            if key not in seen:
                cleaned.append(display_term)
                seen.add(key)
        if len(cleaned) > MAX_TERMS:
            raise ValueError(f"Use até {MAX_TERMS} termos por grupo de origem.")
    return [{"source": url, "terms": terms} for url, terms in result.items() if terms]


def compile_source_blacklists(
    raw: object, sources: tuple[str, ...]
) -> dict[str, tuple[str, ...]]:
    """Prepare whole-word matches for active sources; ignore malformed stored entries."""
    if not isinstance(raw, list):
        return {}
    result = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        source, terms = entry.get("source"), entry.get("terms")
        if isinstance(source, str) and source in sources and isinstance(terms, list):
            result[source] = tuple(
                f" {words} "
                for term in terms
                if isinstance(term, str) and (words := _search_words(term))
            )
    return result


def matches_source_blacklist(title: str | None, terms: tuple[str, ...]) -> bool:
    """Match a whole word or contiguous phrase in the parsed product title."""
    if not title or not terms:
        return False
    words = f" {_search_words(title)} "
    return any(term in words for term in terms)
