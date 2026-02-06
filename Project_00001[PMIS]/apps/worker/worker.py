import os
from celery import Celery

broker = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
celery_app = Celery("worker", broker=broker)


@celery_app.task
def hello_task(name: str = "world"):
    # import shared helper
    try:
        from common import greet
    except Exception:
        def greet(n="world"):
            return f"Hello, {n}! (fallback)"

    return greet(name)
