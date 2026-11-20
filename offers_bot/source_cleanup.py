"""Remove semantic source ads and explicit alert-bot advertising fallbacks."""

import logging
import re


_LOGGER = logging.getLogger(__name__)
_STORE_URL_RE = re.compile(
    r"https?://[^\s<>()]*(?:"
    r"amazon\.|amzn\.to|link\.amazon|shopee\.com\.br|mercadolivre\.com\.br|"
    r"meli\.la|aliexpress\.com|magazineluiza\.com\.br|magalu\.com\.br|"
    r"magazineluiza\.onelink\.me|divulgador\.magalu\.com|kabum\.com\.br|"
    r"tidd\.ly|awin1\.com|cutt\.ly"
    r")",
    re.IGNORECASE,
)
_PRODUCT_LABEL_RE = re.compile(
    r"\b(?:(?:link\s+(?:do\s+)?(?:produto|carrinho)|compre\s+aqui)\b|"
    r"(?:produto|carrinho)\s*:)",
    re.IGNORECASE,
)
_AD_SIGNAL_RE = re.compile(
    r"\b(?:bot|rob[oô]|alertas?|avisos?|canal|grupo|siga|inscreva|participe|"
    r"entre|convite|comunidade|monitoramento)\b|"
    r"https?://(?:t\.me|telegram\.me)/|@[A-Za-z][A-Za-z0-9_]{3,}",
    re.IGNORECASE,
)
_PRICE_OR_COUPON_RE = re.compile(
    r"R\$\s*\d|\bcupom\s*:|\bdesconto\b.*\bOFF\b", re.IGNORECASE
)
_STORE_INVITATION_RE = re.compile(
    r"^[\W_]*(?:entre|participe|siga|inscreva-se)\b[^\n:]*"
    r"\b(?:grupo|canal|comunidade)\b",
    re.IGNORECASE,
)
_ALERT_LABEL_RE = re.compile(
    r"^[\W_]*(?:bot|rob[oô])\s+(?:(?:de|para)\s+)?"
    r"(?:alertas?|avisos?|monitoramento)[\W_]*$",
    re.IGNORECASE,
)
_TELEGRAM_DESTINATION = (
    r"(?:https?://(?:t\.me|telegram\.me)/[A-Za-z0-9_]+(?:\?[^\s<>()]*)?"
    r"|@[A-Za-z][A-Za-z0-9_]{3,})"
)
_DESTINATION_RE = re.compile(_TELEGRAM_DESTINATION, re.IGNORECASE)
_DESTINATION_LINE_RE = re.compile(
    rf"^[\W_]*(?:\[[^\]\n]+\]\({_TELEGRAM_DESTINATION}\)"
    rf"|{_TELEGRAM_DESTINATION})[\W_]*$",
    re.IGNORECASE,
)


def _protected_span_ad_ranges(span: str, start: int) -> list[tuple[int, int]]:
    """Remove only ad-only lines inside a span that also carries deal content."""
    ranges = []
    offset = 0
    for line in span.splitlines(keepends=True):
        stripped = line.strip()
        if (
            stripped
            and _AD_SIGNAL_RE.search(stripped)
            and not _PRODUCT_LABEL_RE.search(stripped)
            and not _PRICE_OR_COUPON_RE.search(stripped)
            and (
                not _STORE_URL_RE.search(stripped)
                or _STORE_INVITATION_RE.match(stripped)
            )
        ):
            ranges.append((start + offset, start + offset + len(line)))
        offset += len(line)
    return ranges


def _alert_advertising_ranges(text: str) -> list[tuple[int, int]]:
    """Locate explicit alert-bot labels paired with Telegram destinations only."""
    lines = text.splitlines(keepends=True)
    ranges = []
    offset = 0
    for index, line in enumerate(lines):
        label = _DESTINATION_RE.sub("", line)
        if _ALERT_LABEL_RE.fullmatch(label.strip()):
            if _DESTINATION_RE.search(line):
                ranges.append((offset, offset + len(line)))
            else:
                destination_index = index + 1
                while (
                    destination_index < len(lines)
                    and not lines[destination_index].strip()
                ):
                    destination_index += 1
                if destination_index < len(lines) and _DESTINATION_LINE_RE.fullmatch(
                    lines[destination_index].strip()
                ):
                    stop = offset + sum(
                        len(part) for part in lines[index : destination_index + 1]
                    )
                    ranges.append((offset, stop))
        offset += len(line)
    return ranges


def clean_source_advertising(text: str, spans: list[str]) -> str:
    """Remove exact LLM spans and explicit alert-bot ads before outgoing additions.

    Match against the unchanged input before merging overlapping ranges. Ignore
    invented, empty, ambiguous, malformed or deal-content spans. A conservative
    label/destination fallback also runs when LLM decisions are missing or
    parsing failed.
    """
    if not isinstance(spans, list):
        spans = []
    ranges = _alert_advertising_ranges(text)
    for span in spans:
        if not isinstance(span, str) or not span.strip():
            continue
        start = text.find(span)
        if start == -1 or text.find(span, start + 1) != -1:
            continue
        if _STORE_URL_RE.search(span):
            _LOGGER.warning(
                "Advertising span contains offer link or deal content; "
                "removing only ad-only lines"
            )
            ranges.extend(_protected_span_ad_ranges(span, start))
            continue
        ranges.append((start, start + len(span)))
    if not ranges:
        return text

    kept: list[str] = []
    end = 0
    for start, stop in sorted(ranges):
        if start > end:
            kept.append(text[end:start])
        end = max(end, stop)
    kept.append(text[end:])
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()
