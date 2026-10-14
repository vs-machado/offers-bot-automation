from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.source_groups import normalize_source


class SourceGroupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    label: str = Field(min_length=1, max_length=100)
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def canonical_url(cls, value: str) -> str:
        return normalize_source(value)

    @field_validator("label", mode="before")
    @classmethod
    def clean_label(cls, value):
        return value.strip() if isinstance(value, str) else value


class SourceGroupRead(SourceGroupWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
