"""Per-platform editorial sampling with owned destination overrides."""

import hashlib
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.credentials import decrypt_config

Percent = Annotated[int, Field(strict=True, ge=0, le=100)]
CONFIG_TYPE = "gaming_policy"
GAMING_TITLE = re.compile(
    r"\b(gamer|gaming|games|gamepad|playstation|ps[345]|xbox|nintendo|steam\s?deck|"
    r"dualsense|dualshock|geforce|rtx|gtx|radeon|rx\s?\d{3,4}|placa[s]? de video|"
    r"gpu|console|joystick|ultragear|rog|tuf|hyperx|redragon|razer|logitech g\d+|"
    r"g pro|g502|g305|g203|g403|g29|g920|g923|8bitdo|gamesir|flydigi)\b"
)


class GamingPolicy(BaseModel):
    """Percentage of gaming offers retained; all other offers remain eligible."""

    model_config = ConfigDict(extra="forbid")
    platforms: dict[Literal["telegram", "whatsapp"], Percent] = Field(
        default_factory=dict
    )
    destinations: dict[str, Percent] = Field(default_factory=dict, max_length=500)

    def keep_percent(self, platform: str, chat_id: str) -> int:
        return self.destinations.get(chat_id, self.platforms.get(platform, 100))


def normalized_title(title: str) -> str:
    return " ".join(
        "".join(
            char
            for char in unicodedata.normalize("NFKD", title.casefold())
            if not unicodedata.combining(char)
        ).split()
    )


def is_gaming_offer(title: str, product: dict | None = None) -> bool:
    """Use per-product semantic classification, with explicit title signals as fallback."""
    return bool(
        (product or {}).get("is_gaming") is True
        or GAMING_TITLE.search(normalized_title(title))
    )


def accepts_gaming(
    policy: GamingPolicy, user_id: int, platform: str, chat_id: str, key: str
) -> bool:
    """Stable sampling avoids rerolling skipped products on retries or across sources."""
    percent = policy.keep_percent(platform, chat_id)
    bucket = (
        int.from_bytes(
            hashlib.sha256(
                f"gaming-v1\0{user_id}\0{platform}\0{key}".encode()
            ).digest()[:8],
            "big",
        )
        % 100
    )
    return bucket < percent


def load_gaming_policy(conn, user_id: int) -> GamingPolicy:
    """Read current encrypted user policy on admission and before delivery."""
    row = conn.execute(
        "SELECT config_data FROM user_configs WHERE user_id=%s AND config_type=%s ORDER BY id LIMIT 1",
        (user_id, CONFIG_TYPE),
    ).fetchone()
    return (
        GamingPolicy.model_validate(decrypt_config(row[0], user_id, CONFIG_TYPE))
        if row
        else GamingPolicy()
    )
