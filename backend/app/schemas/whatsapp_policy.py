"""Validated editorial limits shared by the API and posting workers."""

import os

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
    account_interval_seconds: int = Field(default=30, ge=1, le=600)
    channel_interval_seconds: int = Field(default=60, ge=1, le=600)
    max_per_hour: int = Field(default=60, ge=1, le=3600)
    max_per_day: int = Field(default=300, ge=1, le=10000)
    burst_window_seconds: int = Field(default=60, ge=5, le=300)
    burst_threshold: int = Field(default=6, ge=6, le=100)
    start_hour_utc: int = Field(default=0, ge=0, le=23)
    end_hour_utc: int = Field(default=24, ge=1, le=24)

    @model_validator(mode="after")
    def validate_window(self):
        if self.ttl_seconds < self.burst_window_seconds + 30:
            raise ValueError(
                "A validade deve superar a janela de coleta em pelo menos 30 segundos."
            )
        if self.start_hour_utc >= self.end_hour_utc:
            raise ValueError("O início deve ser anterior ao fim da janela UTC.")
        if self.max_per_day < self.max_per_hour:
            raise ValueError("O limite diário deve ser maior ou igual ao horário.")
        return self
