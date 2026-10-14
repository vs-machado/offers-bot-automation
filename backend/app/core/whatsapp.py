"""Tenant-scoped WAHA access; operator credentials never reach browser clients."""

import base64
import mimetypes
import os
import re
from urllib.parse import quote, urlparse

import httpx

from backend.worker.poster import BotPosterError

GROUP_ID = re.compile(r"^\d+(?:-\d+)?@g\.us$")
CHANNEL_ID = re.compile(r"^\d+@newsletter$")


def session_name(user_id: int) -> str:
    """Derive an isolated session from authenticated application identity."""
    return f"offers-user-{user_id}"


class WahaClient:
    def __init__(self, user_id: int):
        if not isinstance(user_id, int) or user_id < 1:
            raise ValueError("Authenticated user ID is required")
        self.session = session_name(user_id)
        self.base_url = os.getenv("WAHA_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("WAHA_API_KEY", "")

    async def request(self, method: str, path: str, body=None, timeout=20):
        """Call a fixed WAHA endpoint without exposing upstream response details."""
        if not self.base_url or not self.api_key:
            raise BotPosterError(
                "Integração WhatsApp não configurada pelo administrador."
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}/api/{path}",
                headers={"X-Api-Key": self.api_key},
                json=body,
            )
        if response.is_error:
            raise BotPosterError(
                "WhatsApp indisponível. Confira conexão e permissões do grupo.",
                status_code=response.status_code,
            )
        return response

    async def status(self) -> dict:
        """Return only connection state and account display name for this tenant."""
        if not self.base_url or not self.api_key:
            return {"status": "UNCONFIGURED", "name": None}
        try:
            response = await self.request("GET", f"sessions/{self.session}")
        except BotPosterError as exc:
            if exc.status_code == 404:
                return {"status": "STOPPED", "name": None}
            raise
        data = response.json()
        return {
            "status": data.get("status", "STOPPED"),
            "name": (data.get("me") or {}).get("pushName"),
        }

    async def start(self) -> dict:
        """Create or resume this tenant's session; never restart a working account."""
        try:
            response = await self.request("GET", f"sessions/{self.session}")
        except BotPosterError as exc:
            if exc.status_code != 404:
                raise
            await self.request(
                "POST", "sessions", {"name": self.session, "start": True}
            )
        else:
            state = response.json().get("status")
            if state == "FAILED":
                await self.request("POST", f"sessions/{self.session}/restart")
            elif state == "STOPPED":
                await self.request("POST", f"sessions/{self.session}/start")
        return await self.status()

    async def qr(self) -> str:
        """Return a private QR data URI; do not cache or send it to third parties."""
        response = await self.request("GET", f"{self.session}/auth/qr")
        if not response.headers.get("content-type", "").startswith("image/png"):
            raise BotPosterError("QR ainda não disponível. Aguarde e tente novamente.")
        return "data:image/png;base64," + base64.b64encode(response.content).decode()

    async def groups(self) -> list[dict]:
        """Expose only group IDs and names from the tenant's connected account."""
        if (await self.status())["status"] != "WORKING":
            raise BotPosterError("Conecte seu WhatsApp antes de selecionar grupos.")
        response = await self.request("GET", f"{self.session}/groups")
        data = response.json()
        if isinstance(data, dict):
            data = list(data.values())
        if not isinstance(data, list):
            raise BotPosterError("Não foi possível listar os grupos do WhatsApp.")
        groups = []
        for group in data:
            identity = group.get("id")
            if isinstance(identity, dict):
                identity = identity.get("_serialized")
            if isinstance(identity, str) and GROUP_ID.fullmatch(identity):
                groups.append(
                    {
                        "id": identity,
                        "name": group.get("subject")
                        or group.get("name")
                        or (group.get("groupMetadata") or {}).get("subject")
                        or identity,
                    }
                )
        return groups

    async def verify_group(self, chat_id: str) -> None:
        """Reject arbitrary IDs and groups outside the authenticated account."""
        if not GROUP_ID.fullmatch(chat_id) or not any(
            group["id"] == chat_id for group in await self.groups()
        ):
            raise BotPosterError("Selecione um grupo da sua conta WhatsApp conectada.")
        response = await self.request(
            "GET", f"{self.session}/groups/{quote(chat_id, safe='')}"
        )
        group = response.json()
        group = group.get("groupMetadata") or group
        if group.get("announce") or group.get("isAnnounce"):
            me = (await self.request("GET", f"sessions/{self.session}/me")).json()
            me_id = me.get("id")
            participants = group.get("participants", [])
            if not any(
                (
                    p.get("id", {}).get("_serialized")
                    if isinstance(p.get("id"), dict)
                    else p.get("id")
                )
                == me_id
                and (
                    p.get("isAdmin")
                    or p.get("isSuperAdmin")
                    or p.get("role") in ("admin", "superadmin")
                )
                for p in participants
            ):
                raise BotPosterError(
                    "Sua conta precisa ser administradora para publicar neste grupo."
                )

    async def channels(self) -> list[dict]:
        """List only channels the tenant owns or administers, never followed channels."""
        if (await self.status())["status"] != "WORKING":
            raise BotPosterError("Conecte seu WhatsApp antes de selecionar canais.")
        response = await self.request("GET", f"{self.session}/channels")
        data = response.json()
        if not isinstance(data, list):
            raise BotPosterError("Não foi possível listar canais do WhatsApp.")
        return [
            {"id": channel["id"], "name": channel.get("name") or channel["id"]}
            for channel in data
            if isinstance(channel.get("id"), str)
            and CHANNEL_ID.fullmatch(channel["id"])
            and channel.get("role") in ("OWNER", "ADMIN")
        ]

    async def verify_destination(self, chat_id: str, chat_type: str) -> None:
        """Require group membership or channel publishing role in the tenant account."""
        if chat_type == "group":
            await self.verify_group(chat_id)
        elif chat_type != "channel" or not any(
            channel["id"] == chat_id for channel in await self.channels()
        ):
            raise BotPosterError("Selecione um canal que você administra no WhatsApp.")

    async def disconnect(self) -> None:
        """Remove linked device and session data belonging to this tenant only."""
        try:
            await self.request("DELETE", f"sessions/{self.session}")
        except BotPosterError as exc:
            if exc.status_code != 404:
                raise

    async def send_offer(self, chat_id, text, image_file=None, request_timeout=20):
        """Send prepared text/photo through the tenant's linked WhatsApp account."""
        if not (GROUP_ID.fullmatch(chat_id) or CHANNEL_ID.fullmatch(chat_id)):
            raise BotPosterError("Destino WhatsApp inválido.")
        body = {"session": self.session, "chatId": chat_id}
        if image_file:
            mimetype = "image/jpeg"
            if image_file.startswith(("https://", "http://")):
                file = {"url": image_file}
                guessed, _ = mimetypes.guess_type(urlparse(image_file).path)
                if guessed and guessed.startswith("image/"):
                    mimetype = guessed
            else:
                with open(image_file, "rb") as stream:
                    content = stream.read()
                if content.startswith(b"\x89PNG\r\n\x1a\n"):
                    mimetype = "image/png"
                elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
                    mimetype = "image/webp"
                file = {"data": base64.b64encode(content).decode()}
            body.update(
                file={
                    "mimetype": mimetype,
                    "filename": "oferta"
                    + (mimetypes.guess_extension(mimetype) or ".jpg"),
                    **file,
                },
                caption=text,
            )
            path = "sendImage"
        else:
            body["text"] = text
            path = "sendText"
        return (await self.request("POST", path, body, timeout=request_timeout)).json()
