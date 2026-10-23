"""Credential probes accept secrets but return only safe validation outcomes."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ProviderType = Literal["amazon", "mercado_livre", "shopee", "aliexpress", "awin"]


class CredentialValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: ProviderType
    config_data: dict[str, SecretStr] = Field(max_length=8)
    product_url: str | None = Field(default=None, max_length=2000)


class CredentialValidationResult(BaseModel):
    provider: ProviderType
    status: Literal["valid", "invalid", "inconclusive"]
    reason: str
    message: str
    checked_at: datetime
