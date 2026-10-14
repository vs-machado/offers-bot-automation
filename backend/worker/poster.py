import os
from dataclasses import dataclass

import httpx


class BotPosterError(RuntimeError):
    """Raised when Telegram bot configuration or posting request fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: int | None = None,
        reason_code: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.reason_code = reason_code


@dataclass(frozen=True)
class BotPoster:
    """Async client for posting offers through the shared Telegram bot."""

    token: str | None = None

    @property
    def _token(self) -> str:
        token = self.token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise BotPosterError(
                "TELEGRAM_BOT_TOKEN is not configured", reason_code="bot_token_missing"
            )
        return token

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    async def send_offer(
        self,
        chat_id: str,
        text: str,
        image_file: str | None = None,
        parse_mode: str | None = None,
        request_timeout: float = 20,
    ) -> dict:
        """Send text or photo offer to chat and return Telegram result payload."""
        payload = {"chat_id": chat_id}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        method = "sendPhoto" if image_file else "sendMessage"
        files = None
        if image_file:
            payload["caption"] = text
            if image_file.startswith(("https://", "http://")):
                payload["photo"] = image_file
            else:
                files = {"photo": open(image_file, "rb")}
        else:
            payload["text"] = text

        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                if files:
                    response = await client.post(
                        self._url(method), data=payload, files=files
                    )
                else:
                    response = await client.post(self._url(method), json=payload)
        finally:
            if files:
                files["photo"].close()
        try:
            data = response.json()
        except ValueError as exc:
            raise BotPosterError(
                "Telegram returned an invalid response",
                reason_code="delivery_uncertain",
            ) from exc
        if response.status_code >= 400 or not data.get("ok"):
            description = data.get("description", response.text)
            raise BotPosterError(
                f"Telegram Bot API {method} failed: {description}",
                status_code=data.get("error_code", response.status_code),
                retry_after=data.get("parameters", {}).get("retry_after"),
            )
        return data["result"]

    async def can_post(self, chat_id: str) -> bool:
        """Return whether configured bot is administrator or creator in chat."""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self._url("getMe"))
            me = response.json()
            if response.status_code >= 400 or not me.get("ok"):
                return False

            bot_id = me["result"]["id"]
            response = await client.post(
                self._url("getChatMember"),
                json={"chat_id": chat_id, "user_id": bot_id},
            )
        data = response.json()
        if response.status_code >= 400 or not data.get("ok"):
            return False

        member = data["result"]
        status = member.get("status")
        return status == "administrator" or status == "creator"
