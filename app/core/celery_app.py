"""
Celery application configuration.

Configures Celery with Redis as the message broker and result backend.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "vyloc",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.localization_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge task after completion (for reliability)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    worker_concurrency=4,  # Number of concurrent workers
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=360,  # 6 minutes hard limit
    
    # Retry settings
    task_default_retry_delay=30,  # 30 seconds between retries
    task_max_retries=3,
)

# Optional: Configure task routing for different queues
celery_app.conf.task_routes = {
    "app.tasks.localization_tasks.*": {"queue": "localization"},
}
