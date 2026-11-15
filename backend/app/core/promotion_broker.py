"""Publish short-lived promotion jobs from the API without loading worker runtime."""

from datetime import datetime
import os

from celery import Celery

QUEUE = "promotions"
TASK = "promotions.post"


def _client() -> Celery:
    app = Celery(
        "offers_api", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    app.conf.update(
        task_default_queue=QUEUE,
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        task_publish_retry=False,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
        enable_utc=True,
    )
    return app


def enqueue_promotion(
    *,
    identity: str,
    user_id: int,
    chat_id: str,
    text: str,
    deadline: float,
    expires_at: datetime,
    image_url: str | None = None,
    parse_mode: str | None = "Markdown",
    category: str = "other",
) -> None:
    """Send one delivery task to the shared worker queue; failures propagate."""
    app = _client()
    try:
        app.send_task(
            TASK,
            kwargs={
                "identity": identity,
                "user_id": user_id,
                "chat_id": chat_id,
                "text": text,
                "deadline": deadline,
                "image_data": None,
                "image_url": image_url,
                "parse_mode": parse_mode,
                "category": category,
            },
            task_id=identity,
            expires=expires_at,
            queue=QUEUE,
        )
    finally:
        app.close()
