"""Redis broker for short-lived delivery tasks; no periodic scheduler required."""

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = Celery(
    "offers_posting",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["backend.worker.posting_queue"],
)
app.conf.update(
    task_default_queue="promotions",
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=False,
    task_publish_retry=False,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 300,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
    },
    timezone="UTC",
    enable_utc=True,
)
