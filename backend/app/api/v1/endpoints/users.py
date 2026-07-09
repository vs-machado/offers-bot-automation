import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.db.session import get_db
from backend.app.models.user import DestinationChannel, Offer, User, UserConfig
from backend.app.schemas.user import (
    DestinationChannelCreate,
    DestinationChannelRead,
    SourceGroupPreviewRequest,
    UserConfigCreate,
    UserConfigRead,
    UserRead,
)
from backend.app.schemas.offer import OfferCreate, OfferRead
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.source_groups import DEFAULT_SOURCE_GROUP_URLS
from backend.worker.poster import BotPoster, BotPosterError

router = APIRouter()


REQUIRED_CONFIG_KEYS = {
    "telegram": ("api_id", "api_hash"),
    "amazon": ("amazon_affiliate_tag", "amazon_cookie_header"),
    "mercado_livre": ("ml_affiliate_tag", "ml_cookie_header", "ml_csrf_token"),
    "shopee": ("shopee_app_id", "shopee_app_secret"),
    "aliexpress": ("aliexpress_app_key", "aliexpress_app_secret"),
}


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
        class_name = attr_map.get("class", "")
        classes = class_name.split()

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
            self._current_message["post_url"] = urljoin(
                "https://t.me/",
                str(attr_map["data-post"]),
            )

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


def _absolute_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return urljoin("https://t.me/", url)


def _clean_message_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _public_telegram_url(chat: str) -> str | None:
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


def _source_group_response(
    source_chats: list[str],
) -> dict[str, list[dict[str, object]]]:
    return {
        "groups": [
            {"id": chat, "label": f"Source option {index + 1}", "messages": []}
            for index, chat in enumerate(source_chats)
        ]
    }


async def _preview_source_groups(
    source_chats: list[str],
) -> dict[str, list[dict[str, object]]]:
    groups = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    ) as client:
        for index, chat in enumerate(source_chats):
            messages = []
            public_url = _public_telegram_url(chat)
            if public_url:
                try:
                    response = await client.get(public_url)
                    response.raise_for_status()
                    parser = TelegramMessageHTMLParser()
                    parser.feed(response.text)
                    messages = [
                        {"id": message_index, **message}
                        for message_index, message in enumerate(parser.messages[-5:], 1)
                    ]
                except Exception:
                    messages = []

            groups.append(
                {
                    "id": chat,
                    "label": f"Source option {index + 1}",
                    "messages": messages,
                }
            )

    return {"groups": groups}


def _validate_config(config_data: UserConfigCreate) -> None:
    required_keys = REQUIRED_CONFIG_KEYS.get(config_data.config_type)
    if not required_keys:
        return

    missing = [
        key for key in required_keys if not str(config_data.config_data.get(key, ""))
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Missing required {config_data.config_type} config keys",
                "missing_keys": missing,
            },
        )


async def _verify_destination_enabled(chat_id: str, enabled: bool) -> None:
    if not enabled:
        return
    try:
        can_post = await BotPoster().can_post(chat_id)
    except BotPosterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not can_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot cannot post to this destination",
        )


@router.get("/me/configs", response_model=list[UserConfigRead])
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(UserConfig).where(UserConfig.user_id == current_user.id)
    result = await db.execute(statement)
    configs = result.scalars().all()
    for c in configs:
        c.config_data = json.loads(c.config_data)
    return configs


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/me/source-groups/messages")
async def list_source_group_messages(
    current_user: User = Depends(get_current_user),
):
    return await _preview_source_groups(DEFAULT_SOURCE_GROUP_URLS)


@router.post("/me/source-groups/preview")
async def preview_source_group(
    preview_data: SourceGroupPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    chat = preview_data.chat.strip()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source group URL or ID is required",
        )

    response = await _preview_source_groups([chat])
    groups = response["groups"]
    if groups:
        groups[0]["label"] = "Custom source"
    return response


@router.post(
    "/me/configs", response_model=UserConfigRead, status_code=status.HTTP_201_CREATED
)
async def create_config(
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_config(config_data)
    new_config = UserConfig(
        user_id=current_user.id,
        config_type=config_data.config_type,
        config_data=json.dumps(config_data.config_data),
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    new_config.config_data = json.loads(new_config.config_data)
    return new_config


@router.put("/me/configs/{config_id}", response_model=UserConfigRead)
async def update_config(
    config_id: int,
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_config(config_data)
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Config not found"
        )

    config.config_type = config_data.config_type
    config.config_data = json.dumps(config_data.config_data)
    await db.commit()
    await db.refresh(config)
    config.config_data = json.loads(config.config_data)
    return config


@router.delete("/me/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Config not found"
        )

    await db.delete(config)
    await db.commit()


@router.get("/me/destinations", response_model=list[DestinationChannelRead])
async def list_destinations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(DestinationChannel).where(
        DestinationChannel.user_id == current_user.id
    )
    result = await db.execute(statement)
    return result.scalars().all()


@router.post(
    "/me/destinations",
    response_model=DestinationChannelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_destination(
    destination_data: DestinationChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_destination_enabled(
        destination_data.chat_id, destination_data.enabled
    )
    new_destination = DestinationChannel(
        user_id=current_user.id,
        chat_id=destination_data.chat_id,
        title=destination_data.title,
        chat_type=destination_data.chat_type,
        enabled=destination_data.enabled,
    )
    db.add(new_destination)
    await db.commit()
    await db.refresh(new_destination)
    return new_destination


@router.put("/me/destinations/{destination_id}", response_model=DestinationChannelRead)
async def update_destination(
    destination_id: int,
    destination_data: DestinationChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found"
        )

    await _verify_destination_enabled(
        destination_data.chat_id, destination_data.enabled
    )

    destination.chat_id = destination_data.chat_id
    destination.title = destination_data.title
    destination.chat_type = destination_data.chat_type
    destination.enabled = destination_data.enabled
    await db.commit()
    await db.refresh(destination)
    return destination


@router.delete(
    "/me/destinations/{destination_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_destination(
    destination_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found"
        )

    await db.delete(destination)
    await db.commit()


@router.get("/me/offers", response_model=list[OfferRead])
async def list_offers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Offer).where(Offer.user_id == current_user.id)
    result = await db.execute(statement)
    return result.scalars().all()


@router.post(
    "/me/offers", response_model=OfferRead, status_code=status.HTTP_201_CREATED
)
async def create_offer(
    offer_data: OfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_offer = Offer(
        user_id=current_user.id,
        platform=offer_data.platform,
        product_url=offer_data.product_url,
        title=offer_data.title,
        price=offer_data.price,
        currency=offer_data.currency,
        affiliate_url=offer_data.affiliate_url,
    )
    db.add(new_offer)
    await db.commit()
    await db.refresh(new_offer)
    return new_offer


@router.put("/me/offers/{offer_id}", response_model=OfferRead)
async def update_offer(
    offer_id: int,
    offer_data: OfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found"
        )

    offer.platform = offer_data.platform
    offer.product_url = offer_data.product_url
    offer.title = offer_data.title
    offer.price = offer_data.price
    offer.currency = offer_data.currency
    offer.affiliate_url = offer_data.affiliate_url
    await db.commit()
    await db.refresh(offer)
    return offer


@router.delete("/me/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(
    offer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found"
        )

    await db.delete(offer)
    await db.commit()
