"""Owner website metadata and rotation rules; no outbound website credentials."""

import ipaddress
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def website_origin(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    try:
        is_public_host = ipaddress.ip_address(host).is_global
    except ValueError:
        is_public_host = "." in host and not host.endswith((".localhost", ".local"))
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
        or not is_public_host
    ):
        raise ValueError(
            "Use a origem HTTPS pública do seu site, sem caminho, usuário ou parâmetros."
        )
    return f"https://{host}"


class WebsiteSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    website_url: str = Field(default="", max_length=255)
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
        if self.enabled and (not self.website_url or not self.connection_id):
            raise ValueError("Para habilitar, informe site e conexão WhatsApp.")
        return self


class WebsiteRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_id: int = Field(gt=0)
