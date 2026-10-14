"""Read-only delivery history; normalize stale queue state without replaying it."""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.delivery_errors import REASONS
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery as Delivery


async def get_delivery_history(
    db: AsyncSession, user_id: int, page: int, limit: int, status: str | None
) -> dict:
    """Return bounded, tenant-scoped history and totals for all delivery states."""
    effective_status = case(
        (
            Delivery.status.in_(("queued", "retrying"))
            & (Delivery.expires_at <= func.now()),
            "expired",
        ),
        (
            (Delivery.status == "sending") & (Delivery.expires_at <= func.now()),
            "uncertain",
        ),
        else_=Delivery.status,
    )
    counts_result = await db.execute(
        select(effective_status.label("status"), func.count())
        .where(Delivery.user_id == user_id)
        .group_by(effective_status)
    )
    counts = dict(counts_result.all())
    destination_title = (
        select(DestinationChannel.title)
        .where(
            DestinationChannel.user_id == user_id,
            DestinationChannel.chat_id == Delivery.chat_id,
        )
        .order_by(DestinationChannel.id)
        .limit(1)
        .correlate(Delivery)
        .scalar_subquery()
    )
    statement = select(
        Delivery,
        effective_status.label("effective_status"),
        destination_title.label("destination_title"),
    ).where(Delivery.user_id == user_id)
    if status:
        statement = statement.where(effective_status == status)
    result = await db.execute(
        statement.order_by(Delivery.created_at.desc(), Delivery.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = []
    for delivery, current_status, title in result.all():
        reason = delivery.reason
        if current_status == "expired" and not reason:
            reason = "promotion_expired"
        elif current_status == "uncertain" and delivery.status == "sending":
            reason = "sending_interrupted"
        elif current_status == "uncertain" and not reason:
            reason = "delivery_uncertain"
        elif current_status == "failed" and not reason:
            reason = (
                "processing_failure" if delivery.stage != "posting" else "telegram_api"
            )
        elif current_status == "cancelled" and not reason:
            reason = "destination_disabled_or_removed"
        reason_message = REASONS.get(reason)
        if reason and not reason_message:
            reason_message = "O serviço não conseguiu concluir essa publicação. O motivo detalhado não está disponível neste registro antigo."
        items.append(
            {
                "id": delivery.id,
                "title": delivery.title,
                "platform": delivery.platform,
                "chat_id": delivery.chat_id,
                "destination_title": title,
                "status": current_status,
                "reason": reason,
                "reason_message": reason_message,
                "stage": delivery.stage,
                "attempts": delivery.attempts,
                "created_at": delivery.created_at,
                "updated_at": delivery.updated_at,
            }
        )
    return {
        "items": items,
        "total": counts.get(status, 0) if status else sum(counts.values()),
        "counts": counts,
    }
