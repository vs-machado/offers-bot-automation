"""Website origins are restricted to Pages or explicitly approved custom domains."""

import os
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def website_origin(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    approved = {
        h.strip().lower()
        for h in os.getenv("WEBSITE_ALLOWED_HOSTS", "").split(",")
        if h.strip()
    }
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
        or not (host.endswith(".pages.dev") or host in approved)
    ):
        raise ValueError(
            "Use a origem HTTPS do Cloudflare Pages ou um domínio aprovado pelo administrador."
        )
    return f"https://{host}"


class WebsiteSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    website_url: str = Field(default="", max_length=255)
    update_token: str = Field(default="", max_length=256)
    connection_id: int | None = Field(default=None, gt=0)
    template_destination_id: int | None = Field(default=None, gt=0)
    group_name: str = Field(default="Ofertas", min_length=1, max_length=90)
    description: str = Field(default="", max_length=2048)
    entry_limit: int = Field(default=1000, ge=2, le=1024)
    safety_margin: int = Field(default=24, ge=1, le=1022)

    @field_validator("website_url")
    @classmethod
    def valid_origin(cls, value):
        return website_origin(value.strip())

    @field_validator("group_name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("Informe o nome da série de grupos.")
        return value.strip()

    @model_validator(mode="after")
    def valid_enabled(self):
        if self.enabled and (
            not self.website_url
            or not self.connection_id
            or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", self.update_token)
        ):
            raise ValueError(
                "Para habilitar, informe site, conexão e token de 32–256 caracteres (letras, números, _ ou -)."
            )
        return self


class WebsiteRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_id: int = Field(gt=0)
