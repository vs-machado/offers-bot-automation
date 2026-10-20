"""Adapt shared Telegram-style offer Markdown to WhatsApp text and captions."""

import re


TOKENS = re.compile(
    r"(?P<code>```.*?```|`[^`\n]+`)"
    r"|(?P<link>\[(?P<label>[^\]\n]+)\]\((?P<target>https?://[^\s)]+)\))"
    r"|(?P<url>https?://[^\s<>]+)"
    r"|(?P<bold>\*\*(?P<bold_text>.+?)\*\*)"
    r"|(?P<italic>__(?P<italic_text>.+?)__)"
    r"|(?P<strike>~~(?P<strike_text>.+?)~~)",
    re.DOTALL,
)


def format_whatsapp_offer(text: str) -> str:
    """Convert offer markup and unwrap coupon code spans without rewriting contents.

    Coupons use regular text for readability; affiliate URLs remain unchanged.
    """

    def replace(match: re.Match) -> str:
        if code := match.group("code"):
            return code[3:-3] if code.startswith("```") else code[1:-1]
        if match.group("url"):
            return match.group()
        if match.group("link"):
            label, target = match.group("label", "target")
            return (
                target
                if label == target
                else f"{format_whatsapp_offer(label)} ({target})"
            )
        for kind, marker in (("bold", "*"), ("italic", "_"), ("strike", "~")):
            content = match.group(f"{kind}_text")
            if content is not None:
                return f"{marker}{format_whatsapp_offer(content)}{marker}"
        return match.group()

    return TOKENS.sub(replace, text)
