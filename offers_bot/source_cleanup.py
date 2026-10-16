"""Apply semantic source-advertising decisions from the existing LLM parser."""

import re


def clean_source_advertising(text: str, spans: list[str]) -> str:
    """Remove only exact, unambiguous source substrings identified by the LLM.

    Match against the unchanged input before merging overlapping ranges. Ignore
    invented, empty, ambiguous or malformed spans. With no LLM decisions, leave
    source text intact. Call before appending platform-owned outgoing content.
    """
    if not isinstance(spans, list):
        return text
    ranges: list[tuple[int, int]] = []
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
