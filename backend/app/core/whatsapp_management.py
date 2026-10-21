"""Normalize engine-specific group data and apply tenant-owned WAHA management operations."""

import re
from urllib.parse import quote

import httpx

from backend.app.core.whatsapp import CHANNEL_ID, GROUP_ID, WahaClient
from backend.worker.poster import BotPosterError

GROUP_CAPACITY = 1024


def identity(value) -> str:
    if isinstance(value, dict):
        value = value.get("_serialized") or value.get("id")
    if not isinstance(value, str):
        return ""
    return re.sub(r":\d+@", "@", value).replace("@s.whatsapp.net", "@c.us")


def group_metadata(group: dict) -> dict:
    return {**group, **(group.get("groupMetadata") or {})}


def is_admin(participants: list, me: dict) -> bool:
    own_ids = {identity(me.get(key)) for key in ("id", "lid", "jid")}
    own_ids.discard("")
    return any(
        own_ids.intersection(
            identity(p.get(key)) for key in ("id", "lid", "pn", "phoneNumber", "jid")
        )
        and (
            p.get("isAdmin")
            or p.get("isSuperAdmin")
            or p.get("role") in ("admin", "superadmin")
            or p.get("admin") in ("admin", "superadmin")
        )
        for p in participants
    )


def member_count(data: dict) -> int | None:
    for key in ("size", "participantsCount", "subscribersCount"):
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    participants = data.get("participants")
    if isinstance(participants, list):
        return sum(p.get("role") != "left" for p in participants)
    return None


def next_group_name(source: str, names: list[str]) -> str:
    """Pick the next unused series number, including gaps and case-insensitive matches."""
    base = re.sub(r"\s*#\d+\s*$", "", source).strip()
    highest = 1
    for name in [source, *names]:
        match = re.fullmatch(
            re.escape(base) + r"\s*#(\d+)", name.strip(), re.IGNORECASE
        )
        if match:
            highest = max(highest, int(match[1]))
    suffix = f" #{highest + 1}"
    return base[: 100 - len(suffix)].rstrip() + suffix


def uploaded_photo(value: str | None) -> dict | None:
    if not value:
        return None
    header, data = value.split(",", 1)
    mimetype = header.removeprefix("data:").removesuffix(";base64")
    return {
        "mimetype": mimetype,
        "filename": "group." + mimetype.split("/")[1],
        "data": data,
    }


class WhatsAppManagement:
    def __init__(self, user_id: int, connection_id: int | None = None):
        self.client = (
            WahaClient(user_id)
            if connection_id is None
            else WahaClient(user_id, connection_id)
        )

    def path(self, chat_id: str, kind="groups") -> str:
        pattern = GROUP_ID if kind == "groups" else CHANNEL_ID
        if not pattern.fullmatch(chat_id):
            raise BotPosterError("Destino WhatsApp inválido.")
        return f"{self.client.session}/{kind}/{quote(chat_id, safe='')}"

    async def groups(self) -> list[dict]:
        """Read group capacity without returning phone numbers or participant details."""
        if (await self.client.status())["status"] != "WORKING":
            raise BotPosterError("Conecte seu WhatsApp para gerenciar grupos.")
        data = (
            await self.client.request("GET", f"{self.client.session}/groups")
        ).json()
        if isinstance(data, dict):
            data = list(data.values())
        if not isinstance(data, list):
            raise BotPosterError("Não foi possível listar grupos.")
        me = (
            await self.client.request("GET", f"sessions/{self.client.session}/me")
        ).json()
        result = []
        for group in data:
            chat_id = identity(group.get("id"))
            if not GROUP_ID.fullmatch(chat_id):
                continue
            meta = group_metadata(group)
            count = member_count(meta)
            capacity = meta.get("maxParticipants")
            if (
                not isinstance(capacity, int)
                or isinstance(capacity, bool)
                or capacity <= 0
            ):
                capacity = GROUP_CAPACITY
            result.append(
                {
                    "id": chat_id,
                    "name": meta.get("subject") or meta.get("name") or chat_id,
                    "chat_type": "group",
                    "member_count": count,
                    "capacity": capacity,
                    "capacity_reported": capacity != GROUP_CAPACITY
                    or meta.get("maxParticipants") == GROUP_CAPACITY,
                    "is_full": count >= capacity if count is not None else None,
                    "can_manage": is_admin(meta.get("participants") or [], me),
                }
            )
        return result

    async def group(self, chat_id: str, require_admin=False) -> dict:
        """Verify account membership and admin role before exposing or editing group settings."""
        groups = await self.groups()
        summary = next((group for group in groups if group["id"] == chat_id), None)
        if summary is None:
            raise BotPosterError("Selecione um grupo da sua conta WhatsApp.")
        path = self.path(chat_id)
        meta = group_metadata((await self.client.request("GET", path)).json())
        participants = meta.get("participants")
        if not isinstance(participants, list):
            participants = (
                await self.client.request("GET", f"{path}/participants/v2")
            ).json()
            if not isinstance(participants, list):
                raise BotPosterError("Não foi possível verificar os membros do grupo.")
            meta["participants"] = participants
        me = (
            await self.client.request("GET", f"sessions/{self.client.session}/me")
        ).json()
        can_manage = is_admin(participants, me)
        if require_admin and not can_manage:
            raise BotPosterError(
                "Sua conta precisa ser administradora para gerenciar este grupo."
            )
        settings = (
            await self.client.request(
                "GET", f"{path}/settings/security/messages-admin-only"
            )
        ).json()
        count = member_count(meta)
        capacity = meta.get("maxParticipants")
        reported = (
            isinstance(capacity, int)
            and not isinstance(capacity, bool)
            and capacity > 0
        )
        if not reported:
            capacity = summary["capacity"]
        name = meta.get("subject") or meta.get("name") or summary["name"]
        result = {
            **summary,
            "name": name,
            "description": meta.get("description") or meta.get("desc") or "",
            "member_count": count,
            "capacity": capacity,
            "capacity_reported": reported or summary["capacity_reported"],
            "is_full": count >= capacity if count is not None else None,
            "admins_only": settings.get("adminsOnly")
            if isinstance(settings, dict)
            else None,
            "can_manage": can_manage,
            "suggested_name": next_group_name(
                name, [group["name"] for group in groups]
            ),
        }
        return result

    async def channels(self) -> list[dict]:
        """List publishing channels independently of group API availability."""
        if (await self.client.status())["status"] != "WORKING":
            raise BotPosterError("Conecte seu WhatsApp para gerenciar canais.")
        channels = (
            await self.client.request("GET", f"{self.client.session}/channels")
        ).json()
        if not isinstance(channels, list):
            raise BotPosterError("Não foi possível listar canais.")
        return [
            {
                "id": channel["id"],
                "name": channel.get("name") or channel["id"],
                "chat_type": "channel",
                "member_count": member_count(channel),
                "capacity": None,
                "capacity_reported": False,
                "is_full": None,
                "can_manage": False,
            }
            for channel in channels
            if isinstance(channel.get("id"), str)
            and CHANNEL_ID.fullmatch(channel["id"])
            and channel.get("role") in ("OWNER", "ADMIN")
        ]

    async def channel(self, chat_id: str) -> dict:
        """Verify publishing role and expose subscriber counts without a fictitious group limit."""
        await self.client.verify_destination(chat_id, "channel")
        data = (await self.client.request("GET", self.path(chat_id, "channels"))).json()
        if data.get("role") not in ("OWNER", "ADMIN"):
            raise BotPosterError("Selecione um canal que você administra.")
        return {
            "id": chat_id,
            "name": data.get("name") or chat_id,
            "chat_type": "channel",
            "description": data.get("description") or "",
            "member_count": member_count(data),
            "capacity": None,
            "capacity_reported": False,
            "is_full": None,
            "can_manage": False,
        }

    async def source_photo(self, chat_id: str) -> dict | None:
        """Reuse only the photo URL supplied by the verified group's WAHA response."""
        data = (
            await self.client.request("GET", f"{self.path(chat_id)}/picture")
        ).json()
        url = data.get("url")
        return (
            {"url": url}
            if isinstance(url, str) and url.startswith(("https://", "http://"))
            else None
        )

    async def create(self, name: str) -> str:
        """Create a group with no copied members; unknown upstream outcomes must not be retried."""
        data = (
            await self.client.request(
                "POST",
                f"{self.client.session}/groups",
                {"name": name, "participants": []},
            )
        ).json()
        chat_id = identity(data.get("id") or data.get("gid"))
        if not GROUP_ID.fullmatch(chat_id):
            raise BotPosterError(
                "Criação iniciada, mas sem confirmação. Atualize a lista antes de tentar novamente."
            )
        return chat_id

    async def apply_settings(self, chat_id: str, settings, photo=None) -> list[str]:
        """Apply settings without hiding partial failure or retrying group creation."""
        path = self.path(chat_id)
        operations = [
            (
                "permissão de mensagens",
                "settings/security/messages-admin-only",
                {"adminsOnly": settings.admins_only},
            ),
            ("nome", "subject", {"subject": settings.name}),
            ("descrição", "description", {"description": settings.description}),
        ]
        if photo:
            operations.append(("foto", "picture", {"file": photo}))
        warnings = []
        for label, suffix, body in operations:
            try:
                response = await self.client.request("PUT", f"{path}/{suffix}", body)
                data = response.json() if response.content else True
                if data is False or (
                    isinstance(data, dict) and data.get("success") is False
                ):
                    raise BotPosterError("WhatsApp recusou a alteração.")
            except (BotPosterError, httpx.HTTPError, ValueError):
                warnings.append(
                    f"Não foi possível salvar {label}. Edite o grupo para tentar novamente."
                )
        return warnings
