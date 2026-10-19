"""Validated WhatsApp group drafts; image data never accepts browser-supplied URLs."""

import base64
import binascii
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.offer_categories import OfferCategory

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class GroupSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2048)
    admins_only: bool = True
    photo: str | None = Field(default=None, max_length=7_000_000)
    categories: list[OfferCategory] | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Informe o nome do grupo.")
        return value

    @field_validator("photo")
    @classmethod
    def valid_photo(cls, value):
        if value is None:
            return value
        match = re.fullmatch(r"data:image/(jpeg|png|webp);base64,(.+)", value)
        if not match:
            raise ValueError("Envie uma imagem JPEG, PNG ou WebP.")
        try:
            content = base64.b64decode(match[2], validate=True)
        except binascii.Error as exc:
            raise ValueError("Imagem inválida.") from exc
        signatures = {
            "jpeg": content.startswith(b"\xff\xd8\xff"),
            "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        }
        if not content or len(content) > MAX_PHOTO_BYTES or not signatures[match[1]]:
            raise ValueError("Imagem inválida ou maior que 5 MB.")
        return value


class GroupCreate(GroupSettings):
    request_id: UUID
    source_id: str | None = Field(default=None, pattern=r"^\d+(?:-\d+)?@g\.us$")
    reuse_photo: bool = True


class RoutingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[OfferCategory] | None = None
    enabled: bool = True
