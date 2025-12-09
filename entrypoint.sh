set -e

# Default to running the API server
SERVICE="${SERVICE:-api}"

case "$SERVICE" in
    api)
        echo "🚀 Starting Vyloc API Server..."
        exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1} --loop uvloop --http httptools
        ;;
    worker)
        echo "🔧 Starting Celery Worker..."
        exec celery -A app.core.celery_app worker \
            --loglevel=${LOG_LEVEL:-INFO} \
            --concurrency=${CONCURRENCY:-4} \
            --queues=localization \
            --hostname=worker@%h
        ;;
    both)
        echo "🚀 Starting API Server and Celery Worker..."
        # Start Celery worker in background
        celery -A app.core.celery_app worker \
            --loglevel=${LOG_LEVEL:-INFO} \
            --concurrency=${CONCURRENCY:-2} \
            --queues=localization \
            --hostname=worker@%h &
        
        # Start API server in foreground
        exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1}
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Valid options: api, worker, both"
        exit 1
        ;;
esac
