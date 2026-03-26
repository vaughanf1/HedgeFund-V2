import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "900"))

app = Celery(
    "hedgefund",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.ingest_price",
        "app.tasks.ingest_fundamentals",
        "app.tasks.ingest_insider",
        "app.tasks.ingest_news",
        "app.tasks.scan_market",
        "app.tasks.analyse_opportunity",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "ingest-price": {
            "task": "app.tasks.ingest_price.run",
            "schedule": 300,  # every 5 minutes
        },
        "ingest-fundamentals": {
            "task": "app.tasks.ingest_fundamentals.run",
            "schedule": crontab(hour=6, minute=0),  # daily at 06:00 UTC
        },
        "ingest-insider": {
            "task": "app.tasks.ingest_insider.run",
            "schedule": crontab(hour=7, minute=0),  # daily at 07:00 UTC
        },
        "ingest-news": {
            "task": "app.tasks.ingest_news.run",
            "schedule": 900,  # every 15 minutes
        },
        "scan-market": {
            "task": "app.tasks.scan_market.run",
            "schedule": SCAN_INTERVAL,  # default 900s, configurable via SCAN_INTERVAL_SECONDS
        },
    },
)


@worker_ready.connect
def start_consume_queue(sender, **kwargs):
    """Auto-start the BLPOP consumer when a Celery worker comes online."""
    app.send_task("app.tasks.analyse_opportunity.consume_queue")
