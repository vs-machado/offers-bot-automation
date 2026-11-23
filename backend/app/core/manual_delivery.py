"""Owner-triggered delivery that intentionally bypasses editorial post caps."""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.promotion_broker import enqueue_promotion
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery
from backend.app.schemas.whatsapp_policy import promotion_ttl


class ManualRepostError(Exception):
    """Reject invalid or duplicate manual posts with an HTTP-friendly status."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def compose_manual_text(source: PromotionDelivery) -> str:
    """Reuse the rendered message, or rebuild it from stored delivery fields."""
    if source.text and source.text.strip():
        return source.text
    parts = []
    if source.title:
        parts.append(source.title)
    if source.price:
        parts.append(f"💰 {source.price}")
    if source.coupon:
        parts.append(f"🎟️ Cupom: {source.coupon}")
    if source.affiliate_url:
        parts.append(f"🔗 {source.affiliate_url}")
    return "\n\n".join(parts)


async def repost_delivery(
    db: AsyncSession,
    user_id: int,
    delivery_id: str,
    chat_id: str,
) -> dict:
    """Queue one manual delivery to an owned destination, ignoring quotas and windows."""
    source = (
        await db.execute(
            select(PromotionDelivery).where(
                PromotionDelivery.id == delivery_id,
                PromotionDelivery.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise ManualRepostError("Oferta não encontrada no seu histórico.", 404)

    destination = (
        (
            await db.execute(
                select(DestinationChannel)
                .where(
                    DestinationChannel.user_id == user_id,
                    DestinationChannel.chat_id == chat_id,
                    DestinationChannel.enabled.is_(True),
                )
                .order_by(DestinationChannel.id)
                .limit(1)
                .with_for_update()
            )
        )
        .scalars()
        .first()
    )
    if destination is None:
        raise ManualRepostError("Grupo ou canal de destino não está habilitado.", 404)

    now = datetime.now(timezone.utc)
    offer_key = source.dedup_key or source.id
    existing = (
        await db.execute(
            select(PromotionDelivery.id)
            .where(
                PromotionDelivery.user_id == user_id,
                PromotionDelivery.chat_id == chat_id,
                or_(
                    PromotionDelivery.dedup_key == offer_key,
                    PromotionDelivery.id == offer_key,
                ),
                or_(
                    PromotionDelivery.status.in_(("sending", "sent", "uncertain")),
                    PromotionDelivery.status.in_(("queued", "retrying"))
                    & (PromotionDelivery.expires_at > now),
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        raise ManualRepostError(
            "Esta oferta já foi enviada ou tem um envio pendente ou incerto nesse destino.",
            409,
        )

    text = compose_manual_text(source)
    if not text:
        raise ManualRepostError(
            "A oferta não tem conteúdo suficiente para publicar.", 400
        )

    expires_at = now + timedelta(seconds=promotion_ttl())
    identity = hashlib.sha256(
        f"manual\0{user_id}\0{chat_id}\0{uuid4().hex}".encode()
    ).hexdigest()
    row = PromotionDelivery(
        id=identity,
        user_id=user_id,
        chat_id=chat_id,
        status="queued",
        stage="posting",
        expires_at=expires_at,
        # Keep the publication episode; the manual job's TTL starts at creation.
        source_at=source.source_at or source.created_at,
        created_at=now,
        dedup_key=offer_key,
        title=source.title,
        price=source.price,
        coupon=source.coupon,
        affiliate_url=source.affiliate_url,
        platform=source.platform,
        category=source.category,
        connection_id=(
            destination.connection_id if destination.platform == "whatsapp" else None
        ),
        text=text,
        image_url=source.image_url,
        manual=True,
    )
    db.add(row)
    await db.commit()

    try:
        await asyncio.to_thread(
            enqueue_promotion,
            identity=identity,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            deadline=expires_at.timestamp(),
            expires_at=expires_at,
            image_url=source.image_url,
            parse_mode="Markdown",
            category=source.category or "other",
        )
    except Exception as exc:
        await db.execute(
            update(PromotionDelivery)
            .where(PromotionDelivery.id == identity)
            .values(status="failed", reason="broker_unavailable")
        )
        await db.commit()
        raise ManualRepostError(
            "Não foi possível enfileirar a publicação agora.", 503
        ) from exc

    return {
        "id": identity,
        "status": "queued",
        "chat_id": chat_id,
        "manual": True,
    }
