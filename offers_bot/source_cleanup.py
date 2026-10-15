"""Remove source-only advertising before adding our own outgoing content."""

import re


ALERT_BOT_LABEL_RE = re.compile(
    r"\b(?:bots?|rob[oô]s?|robozinhos?)\s+(?:(?:de|dos?|para)\s+)?"
    r"(?:alertas?|avisos?|monitoramento)\b",
    re.IGNORECASE,
)
ALERT_INVITATION_RE = re.compile(
    r"\b(?:receba|ative|crie|configure|acesse|use|conhe[cç]a)\b.*"
    r"\b(?:alertas?|avisos?)\b",
    re.IGNORECASE,
)
TELEGRAM_DESTINATION_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s)\]>]+|(?<!\w)@[A-Za-z0-9_]+",
    re.IGNORECASE,
)
DESTINATION_ONLY_RE = re.compile(
    r"^[\W_]*(?:(?:https?://)?(?:t\.me|telegram\.me)/[^\s)\]>]+"
    r"|@[A-Za-z0-9_]+)[\W_]*$",
    re.IGNORECASE,
)


def clean_source_advertising(text: str) -> str:
    """Strip alert-bot ads from incoming text, keeping unrelated offer lines.

    Consume a separately wrapped Telegram destination after an advertising
    label, including across blank lines. Apply only to source content, before
    appending any platform-owned footer or future alert-bot promotion.
    """
    kept: list[str] = []
    awaiting_destination = False
    removed_advertising = False
    for line in text.splitlines():
        is_label = ALERT_BOT_LABEL_RE.search(line)
        is_invitation = ALERT_INVITATION_RE.search(line)
        has_destination = TELEGRAM_DESTINATION_RE.search(line)
        if is_label or (is_invitation and has_destination):
            removed_advertising = True
            awaiting_destination = not has_destination
            continue
        if awaiting_destination:
            if not line.strip():
                continue
            awaiting_destination = False
            if DESTINATION_ONLY_RE.fullmatch(line):
                continue
        kept.append(line)
    if not removed_advertising:
        return text
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
