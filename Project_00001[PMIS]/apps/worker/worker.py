import os
import logging
from celery import Celery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

broker = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
celery_app = Celery("worker", broker=broker)


@celery_app.task
def hello_task(name: str = "world"):
    """Simple hello task for testing."""
    try:
        from common import greet
    except Exception:
        def greet(n="world"):
            return f"Hello, {n}! (fallback)"

    return greet(name)


@celery_app.task
def process_task(name: str, data: dict):
    """Process an async task: demo task that echoes input and adds timestamp."""
    import time
    from datetime import datetime

    try:
        from common import greet
        greeting = greet(name)
    except Exception:
        greeting = f"Hello, {name}!"

    logger.info(f"Processing task '{name}' with data: {data}")

    # Simulate some work
    time.sleep(1)

    result = {
        "name": name,
        "greeting": greeting,
        "input_data": data,
        "timestamp": datetime.utcnow().isoformat(),
        "processed": True,
    }

    logger.info(f"Task '{name}' completed: {result}")
    return result
