import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


@dataclass(frozen=True)
class TelegramSourceMessage:
    source_chat: str
    message_id: int
    text: str
    image_url: str | None = None
    post_url: str | None = None
    links: tuple[dict[str, str], ...] = ()


class TelegramMessageHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[dict[str, object]] = []
        self._in_widget_message = False
        self._message_depth = 0
        self._current_message: dict[str, object] | None = None
        self._in_text = False
        self._text_depth = 0
        self._parts: list[str] = []
        self._active_link: dict[str, str] | None = None
        self._active_link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = attr_map.get("class", "").split()

        if tag == "div" and "tgme_widget_message_wrap" in classes:
            self._in_widget_message = True
            self._message_depth = 1
            self._current_message = {"text": "", "links": []}
            self._parts = []
            return

        if not self._in_widget_message:
            return

        if tag == "div":
            self._message_depth += 1

        if (
            tag == "div"
            and "tgme_widget_message" in classes
            and attr_map.get("data-post")
            and self._current_message is not None
        ):
            data_post = str(attr_map["data-post"])
            self._current_message["post_url"] = urljoin("https://t.me/", data_post)
            message_id = data_post.rsplit("/", 1)[-1]
            if message_id.isdigit():
                self._current_message["message_id"] = int(message_id)

        self._capture_image_url(attr_map, classes)

        if (
            tag == "div"
            and "tgme_widget_message_text" in classes
            and "js-message_text" in classes
            and "js-message_reply_text" not in classes
        ):
            self._in_text = True
            self._text_depth = 1
            if self._parts:
                self._parts.append("\n")
            return

        if self._in_text:
            if tag == "div":
                self._text_depth += 1
            if tag in {"br", "p"}:
                self._parts.append("\n")
            if tag == "a":
                href = attr_map.get("href")
                if href:
                    self._active_link = {"url": _absolute_url(href)}
                    self._active_link_parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_widget_message:
            return

        if self._in_text and tag == "a" and self._active_link is not None:
            link_text = _clean_message_text("".join(self._active_link_parts))
            if link_text:
                self._active_link["text"] = link_text
            self._append_link(self._active_link)
            self._active_link = None
            self._active_link_parts = []

        if self._in_text and tag == "div":
            self._text_depth -= 1
            if self._text_depth <= 0:
                self._in_text = False

        if tag != "div":
            return

        self._message_depth -= 1
        if self._message_depth <= 0:
            text = _clean_message_text("".join(self._parts))
            if self._current_message is not None:
                self._current_message["text"] = text
                if text or self._current_message.get("image_url"):
                    self.messages.append(self._current_message)
            self._in_widget_message = False
            self._current_message = None
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_text:
            self._parts.append(data)
            if self._active_link is not None:
                self._active_link_parts.append(data)

    def _capture_image_url(
        self,
        attr_map: dict[str, str | None],
        classes: list[str],
    ) -> None:
        if self._current_message is None or self._current_message.get("image_url"):
            return

        image_classes = {
            "tgme_widget_message_photo_wrap",
            "link_preview_right_image",
            "tgme_widget_message_reply_thumb",
        }
        if not image_classes.intersection(classes):
            return

        style = attr_map.get("style")
        if not style:
            return

        match = re.search(r"background-image:url\(['\"]?([^'\")]+)", style)
        if match:
            self._current_message["image_url"] = _absolute_url(match.group(1))

    def _append_link(self, link: dict[str, str]) -> None:
        if self._current_message is None:
            return

        links = self._current_message.setdefault("links", [])
        if not isinstance(links, list):
            return
        if any(
            isinstance(existing, dict) and existing.get("url") == link.get("url")
            for existing in links
        ):
            return
        links.append(link)


def public_telegram_url(chat: str) -> str | None:
    value = chat.strip()
    if not value:
        return None

    if value.startswith("@"):
        slug = value[1:].strip()
    elif value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.netloc.lower() not in {"t.me", "telegram.me"}:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return None
        if parts[0] == "s":
            parts = parts[1:]
        if not parts:
            return None
        slug = parts[0]
    else:
        slug = value

    if not re.fullmatch(r"[A-Za-z0-9_]{5,64}", slug):
        return None

    return f"https://t.me/s/{slug}"


async def fetch_source_messages(
    chats: list[str],
    *,
    limit: int = 5,
) -> dict[str, list[TelegramSourceMessage]]:
    messages_by_chat: dict[str, list[TelegramSourceMessage]] = {}
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    ) as client:
        for chat in chats:
            messages_by_chat[chat] = []
            public_url = public_telegram_url(chat)
            if not public_url:
                continue

            try:
                response = await client.get(public_url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            parser = TelegramMessageHTMLParser()
            parser.feed(response.text)
            parsed_messages = parser.messages[-limit:]
            for fallback_id, message in enumerate(parsed_messages, 1):
                text = str(message.get("text", ""))
                links = tuple(
                    link
                    for link in message.get("links", [])
                    if isinstance(link, dict) and isinstance(link.get("url"), str)
                )
                messages_by_chat[chat].append(
                    TelegramSourceMessage(
                        source_chat=chat,
                        message_id=int(message.get("message_id", fallback_id)),
                        text=text,
                        image_url=str(message["image_url"])
                        if message.get("image_url")
                        else None,
                        post_url=str(message["post_url"])
                        if message.get("post_url")
                        else None,
                        links=links,
                    )
                )
    return messages_by_chat


def _absolute_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return urljoin("https://t.me/", url)


def _clean_message_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
