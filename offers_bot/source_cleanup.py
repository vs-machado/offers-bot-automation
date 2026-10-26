"""Remove semantic source ads and explicit alert-bot advertising fallbacks."""

import re


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
    invented, empty, ambiguous or malformed spans. A conservative label/destination
    fallback also runs when LLM decisions are missing or parsing failed.
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
