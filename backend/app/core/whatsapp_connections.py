"""Resolve owned connection IDs and serialize routing changes before WAHA calls."""

from fastapi import HTTPException
from sqlalchemy import select

from backend.app.core.whatsapp import WahaClient
from backend.app.models.user import DestinationChannel, User
from backend.app.models.whatsapp_connection import WhatsAppConnection
from backend.app.models.whatsapp_policy import WhatsAppDeliveryPolicy
from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, new_connection_policy


async def owned_connection(db, user_id: int, connection_id: int | None = None):
    """Reject foreign IDs; omitted ID keeps the original primary-session API working."""
    query = select(WhatsAppConnection).where(WhatsAppConnection.user_id == user_id)
    query = (
        query.where(WhatsAppConnection.id == connection_id)
        if connection_id is not None
        else query.where(WhatsAppConnection.is_default.is_(True))
    )
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None and connection_id is not None:
        raise HTTPException(404, "Conexão WhatsApp não encontrada.")
    return row


def client_for(user_id: int, connection: WhatsAppConnection | None):
    return (
        WahaClient(user_id)
        if connection is None or connection.is_default
        else WahaClient(user_id, connection.id)
    )


async def ensure_primary(db, user_id: int):
    """Create the legacy-session record once, serializing concurrent first access."""
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    row = await owned_connection(db, user_id)
    if row is None:
        row = WhatsAppConnection(user_id=user_id, name="Principal", is_default=True)
        db.add(row)
        await db.flush()
        stored = (
            await db.execute(
                select(WhatsAppDeliveryPolicy).where(
                    WhatsAppDeliveryPolicy.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            db.add(
                WhatsAppDeliveryPolicy(
                    user_id=user_id,
                    config_data=new_connection_policy().model_dump_json(),
                )
            )
        # Adopt legacy routing created before the first connection-list request.
        from sqlalchemy import update

        await db.execute(
            update(DestinationChannel)
            .where(
                DestinationChannel.user_id == user_id,
                DestinationChannel.platform == "whatsapp",
                DestinationChannel.connection_id.is_(None),
            )
            .values(connection_id=row.id)
        )
    return row


async def validate_routing(
    db,
    user_id: int,
    connection,
    chat_id: str,
    chat_type: str,
    enabled: bool,
    destination_id: int | None = None,
):
    """Prevent duplicate ownership and enforce enabled-group capacity under a user lock."""
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    if connection is not None:
        await db.refresh(connection)
    rows = list(
        (
            await db.execute(
                select(DestinationChannel)
                .where(
                    DestinationChannel.user_id == user_id,
                    DestinationChannel.platform == "whatsapp",
                )
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    others = [row for row in rows if row.id != destination_id]
    if any(row.chat_id == chat_id for row in others):
        raise HTTPException(
            409,
            "Destino já cadastrado. Edite o destino existente para trocar sua conexão.",
        )
    if not enabled or chat_type != "group":
        return
    stored = None
    if connection is None or connection.is_default:
        stored = (
            await db.execute(
                select(WhatsAppDeliveryPolicy).where(
                    WhatsAppDeliveryPolicy.user_id == user_id
                )
            )
        ).scalar_one_or_none()
    settings = (
        WhatsAppPolicy.model_validate_json(connection.config_data)
        if connection and not connection.is_default and connection.config_data
        else WhatsAppPolicy.model_validate_json(stored.config_data)
        if stored
        else WhatsAppPolicy()
    )
    connection_id = connection.id if connection else None
    count = sum(
        1
        for row in others
        if row.enabled
        and row.chat_type == "group"
        and (
            row.connection_id == connection_id
            or (connection and connection.is_default and row.connection_id is None)
        )
    )
    if count >= settings.max_groups:
        raise HTTPException(
            409,
            f"Esta conexão permite até {settings.max_groups} grupos habilitados. Use outra conexão ou desative um grupo.",
        )
