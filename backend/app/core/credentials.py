"""Authenticated encryption and safe API representations of user configuration."""

import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

PREFIX = "fernet:v1:"
MASK = "********"


def credential_cipher() -> MultiFernet:
    """Load external keys; first key writes, remaining keys support rotation reads."""
    primary = os.getenv("CREDENTIALS_ENCRYPTION_KEY", "").strip()
    if not primary:
        raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY is required")
    previous = os.getenv("CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS", "").strip()
    keys = [primary, *previous.split(",")] if previous else [primary]
    try:
        return MultiFernet([Fernet(key.strip().encode("ascii")) for key in keys])
    except (ValueError, TypeError, UnicodeError):
        raise RuntimeError("Invalid credential encryption key configuration") from None


def encrypt_config(data: Any, user_id: int, config_type: str) -> str:
    """Encrypt complete config, binding authenticated payload to owner and provider."""
    payload = json.dumps(
        {"user_id": user_id, "config_type": config_type, "data": data},
        ensure_ascii=False,
    ).encode("utf-8")
    return PREFIX + credential_cipher().encrypt(payload).decode("ascii")


def decrypt_config(value: str, user_id: int, config_type: str) -> Any:
    """Read encrypted config or legacy JSON during migration; never ignore bad tokens."""
    if not value.startswith(PREFIX):
        return json.loads(value)
    try:
        payload = json.loads(
            credential_cipher().decrypt(value[len(PREFIX) :].encode("ascii"))
        )
        if payload["user_id"] != user_id or payload["config_type"] != config_type:
            raise ValueError
        return payload["data"]
    except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError):
        raise RuntimeError("Unable to decrypt stored user configuration") from None


def is_secret_field(key: str) -> bool:
    key = key.lower()
    return any(
        part in key
        for part in (
            "cookie",
            "secret",
            "token",
            "password",
            "api_key",
            "app_key",
            "api_hash",
            "session",
        )
    )


def mask_config(data: Any) -> Any:
    """Remove secret values from API responses, including nested legacy settings."""
    if isinstance(data, dict):
        return {
            key: MASK if is_secret_field(key) and value else mask_config(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_config(value) for value in data]
    return data


def restore_masked_secrets(data: Any, stored: Any = None) -> Any:
    """Resolve API placeholders against owned config; reject unbacked placeholders."""
    if isinstance(data, list):
        previous = stored if isinstance(stored, list) else []
        return [
            restore_masked_secrets(
                value, previous[index] if index < len(previous) else None
            )
            for index, value in enumerate(data)
        ]
    if not isinstance(data, dict):
        return data
    stored = stored if isinstance(stored, dict) else {}
    restored = {}
    for key, value in data.items():
        if value == MASK:
            if not is_secret_field(key) or not stored.get(key):
                raise ValueError(
                    "Credencial mascarada sem valor salvo. Informe a credencial."
                )
            restored[key] = stored[key]
        elif isinstance(value, (dict, list)):
            restored[key] = restore_masked_secrets(value, stored.get(key))
        else:
            restored[key] = value
    return restored
