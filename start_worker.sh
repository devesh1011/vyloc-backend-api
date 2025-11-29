#!/bin/bash

# Celery worker startup script for Vyloc
# This script starts the Celery worker with the appropriate configuration

# Change to the backend directory
cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check Redis connection
echo "🔍 Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if redis-cli -u "${REDIS_URL:-redis://localhost:6379/0}" ping &> /dev/null; then
        echo "✅ Redis is running"
    else
        echo "❌ Redis is not responding. Please start Redis first."
        echo "   On macOS: brew services start redis"
        echo "   On Linux: sudo systemctl start redis"
        exit 1
    fi
else
    echo "⚠️  redis-cli not found, skipping Redis check"
fi

# Start Celery worker
echo "🚀 Starting Celery worker..."
echo "   Queue: localization"
echo "   Concurrency: 4"

# Use uv to run if available, otherwise use python directly
if command -v uv &> /dev/null; then
    uv run celery -A app.core.celery_app worker \
        --loglevel=INFO \
        --concurrency=4 \
        --queues=localization \
        --hostname=worker@%h
else
    python -m celery -A app.core.celery_app worker \
        --loglevel=INFO \
        --concurrency=4 \
        --queues=localization \
        --hostname=worker@%h
fi
