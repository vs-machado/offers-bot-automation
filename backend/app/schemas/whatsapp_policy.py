"""Validated editorial limits shared by the API and posting workers."""

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


def promotion_ttl() -> int:
    """Return operator validity, bounded by the absolute ten-minute limit."""
    value = int(os.getenv("PROMOTION_TTL_SECONDS", "600"))
    if not 1 <= value <= 600:
        raise ValueError("PROMOTION_TTL_SECONDS must be between 1 and 600")
    return value


class WhatsAppPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl_seconds: int = Field(default=600, ge=30, le=600)
    account_interval_seconds: int = Field(default=20, ge=1, le=600)
    account_interval_max_seconds: int | None = Field(default=None, ge=1, le=600)
    channel_interval_seconds: int = Field(default=45, ge=1, le=600)
    max_per_hour: int = Field(default=90, ge=1, le=3600)
    max_per_day: int = Field(default=600, ge=1, le=10000)
    destination_max_per_day: int | None = Field(default=None, ge=1, le=10000)
    max_groups: int = Field(default=6, ge=1, le=6)
    burst_window_seconds: int = Field(default=60, ge=5, le=300)
    collection_seconds: int = Field(default=10, ge=5, le=300)
    burst_threshold: int = Field(default=6, ge=6, le=100)
    start_hour_utc: int = Field(default=0, ge=0, le=23)
    end_hour_utc: int = Field(default=24, ge=1, le=24)
    posting_timezone: str = Field(default="UTC", max_length=100)

    @model_validator(mode="after")
    def validate_window(self):
        if (
            self.account_interval_max_seconds is not None
            and self.account_interval_max_seconds < self.account_interval_seconds
        ):
            raise ValueError("Intervalo máximo deve ser maior ou igual ao mínimo.")
        try:
            ZoneInfo(self.posting_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso horário inválido.") from exc
        if (
            self.ttl_seconds
            < max(self.burst_window_seconds, self.collection_seconds) + 30
        ):
            raise ValueError(
                "A validade deve superar as janelas de coleta e rajada em pelo menos 30 segundos."
            )
        if self.start_hour_utc >= self.end_hour_utc:
            raise ValueError(
                "O início deve ser anterior ao fim da janela de publicação."
            )
        if self.max_per_day < self.max_per_hour:
            raise ValueError("O limite diário deve ser maior ou igual ao horário.")
        return self


def new_connection_policy() -> WhatsAppPolicy:
    """Explicit editorial defaults for new numbers; existing saved policies are unchanged."""
    return WhatsAppPolicy(
        account_interval_seconds=30,
        account_interval_max_seconds=90,
        channel_interval_seconds=60,
        destination_max_per_day=100,
        start_hour_utc=7,
        end_hour_utc=23,
        posting_timezone="America/Sao_Paulo",
    )
