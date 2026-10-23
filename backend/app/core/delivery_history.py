"""Read-only delivery history; normalize stale queue state without replaying it."""

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.delivery_errors import REASONS
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery as Delivery


async def get_delivery_history(
    db: AsyncSession,
    user_id: int,
    page: int,
    limit: int,
    status: str | None,
    group_by_offer: bool = False,
    platform: str | None = None,
) -> dict:
    """Return owned history, optionally paging whole offers with all their outcomes."""
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
    filters = [Delivery.user_id == user_id]
    if platform:
        # Workers save display labels ("Mercado Livre"); API filters use slugs.
        stored_platform = func.lower(func.replace(Delivery.platform, " ", "_"))
        filters.append(stored_platform == platform)
    counts_result = await db.execute(
        select(effective_status.label("status"), func.count())
        .where(*filters)
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
    # A product key is permanent. Split its audit rows into publication episodes
    # after a gap longer than the offer lifetime; source time keeps slow sends together.
    product_id = func.coalesce(Delivery.dedup_key, Delivery.id)
    occurred_at = func.extract(
        "epoch", func.coalesce(Delivery.source_at, Delivery.created_at)
    )
    timeline = (
        select(
            Delivery.id.label("delivery_id"),
            product_id.label("product_id"),
            occurred_at.label("occurred_at"),
            func.lag(occurred_at)
            .over(partition_by=product_id, order_by=(occurred_at, Delivery.id))
            .label("previous_at"),
        )
        .where(*filters)
        .subquery()
    )
    episodes = select(
        timeline.c.delivery_id,
        timeline.c.product_id,
        func.sum(
            case(
                (timeline.c.previous_at.is_(None), 1),
                (timeline.c.occurred_at - timeline.c.previous_at > 600, 1),
                else_=0,
            )
        )
        .over(
            partition_by=timeline.c.product_id,
            order_by=(timeline.c.occurred_at, timeline.c.delivery_id),
            rows=(None, 0),
        )
        .label("episode"),
    ).subquery()
    offer_id = case(
        (episodes.c.episode == 1, episodes.c.product_id),
        else_=episodes.c.product_id + ":" + cast(episodes.c.episode, String),
    )
    statement = (
        select(
            Delivery,
            effective_status.label("effective_status"),
            destination_title.label("destination_title"),
            offer_id.label("offer_id"),
        )
        .join(episodes, Delivery.id == episodes.c.delivery_id)
        .where(*filters)
    )
    total = counts.get(status, 0) if status else sum(counts.values())
    if group_by_offer:
        # Never merge unrelated legacy rows by title or split destinations by page.
        offers = (
            select(
                offer_id.label("offer_id"),
                func.max(Delivery.created_at).label("latest_at"),
            )
            .join(episodes, Delivery.id == episodes.c.delivery_id)
            .where(*filters)
            .group_by(offer_id)
        )
        if status:
            offers = offers.having(
                func.sum(case((effective_status == status, 1), else_=0)) > 0
            )
        total = await db.scalar(select(func.count()).select_from(offers.subquery()))
        selected_offers = (
            offers.order_by(func.max(Delivery.created_at).desc(), offer_id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .subquery()
        )
        statement = statement.join(
            selected_offers, offer_id == selected_offers.c.offer_id
        ).order_by(
            selected_offers.c.latest_at.desc(),
            selected_offers.c.offer_id.desc(),
            Delivery.created_at.desc(),
            Delivery.id.desc(),
        )
    else:
        if status:
            statement = statement.where(effective_status == status)
        statement = (
            statement.order_by(Delivery.created_at.desc(), Delivery.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    result = await db.execute(statement)
    items = []
    for delivery, current_status, title, publication_id in result.all():
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
                "offer_id": publication_id,
                "title": delivery.title,
                "price": delivery.price,
                "coupon": delivery.coupon,
                "affiliate_url": delivery.affiliate_url,
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
        "total": total,
        "counts": counts,
    }
