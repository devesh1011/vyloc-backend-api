# Vyloc Backend API

**AI-Powered Product Localization Platform - Backend Service**

Transform your product advertisements for global markets using artificial intelligence. Vyloc automatically adapts images to match cultural preferences, demographics, and local aesthetics across 15+ target markets.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Docker Deployment](#docker-deployment)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Background Jobs](#background-jobs)
- [Architecture](#architecture)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Features

### Core Capabilities

- **🌍 Multi-Language Support** - Localize to 15+ languages including Hindi, Japanese, Korean, German, French, Spanish, Chinese, Arabic, Russian, Thai, Vietnamese, Indonesian, and more
- **🎨 Intelligent Image Generation** - Uses Google Gemini 3 Pro Image for state-of-the-art AI-powered image generation
- **👥 Demographic Adaptation** - Automatically changes people/models in images to match target market demographics
- **🌐 Cultural Localization** - Adapts visual elements, colors, and symbols according to cultural preferences
- **📝 Smart Text Translation** - AI-powered text translation that preserves original design layout and typography
- **⚡ Parallel Processing** - Generate localized versions for multiple languages simultaneously via `asyncio.gather()`
- **🎯 Flexible Image Specs** - Support for 1K, 2K, 4K resolutions and multiple aspect ratios (1:1, 9:16, 16:9, 3:4, 4:3)
- **💾 Cloud Storage Integration** - Automatic upload to Google Cloud Storage with public CDN URLs
- **🖼️ Watermark Removal** - AI-based inpainting using PyTorch to remove generated artifacts
- **🔄 Batch Processing** - Cost-effective batch API for processing 50+ images at once (50% lower cost than real-time)
- **📊 Job Tracking** - Real-time job status updates via WebSocket and database persistence

---

## Tech Stack

### Backend Framework

- **FastAPI** `>=0.122.0` - High-performance async Python web framework with auto-generated API docs
- **Uvicorn** `>=0.34.0` - ASGI web server for production deployments
- **Pydantic** `>=2.10.0` - Data validation using Python type hints
- **Pydantic Settings** `>=2.6.0` - Environment variable management

### AI & Image Processing

- **Google GenAI SDK** - Gemini API integration for image generation and text translation
- **Pillow** `>=11.0.0` - Image processing (format conversion, resizing, validation)
- **OpenCV** `>=4.10.0` - Watermark removal via AI inpainting
- **PyTorch** `>=2.0.0` (CPU-only) - Deep learning framework for watermark removal model
- **NumPy** `>=2.0.0` - Numerical operations for image processing

### Data & Storage

- **Supabase** `>=2.10.0` - PostgreSQL database with Realtime subscriptions
- **Google Cloud Storage** `>=2.18.0` - Cloud image storage and CDN delivery
- **Redis** `>=5.0.0` - Message broker for Celery background jobs
- **Celery** `>=5.4.0` - Distributed task queue for background image processing

### Other Services

- **WebSockets** `>=12.0` - Real-time job status updates to clients
- **httpx** `>=0.28.0` - Async HTTP client for external API calls
- **aiofiles** `>=24.1.0` - Async file I/O operations

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── core/
│   │   └── config.py                # Settings, environment variables, CORS configuration
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── localization.py          # Real-time localization endpoints
│   │   ├── batch.py                 # Batch processing endpoints
│   │   ├── payments.py              # Stripe payment integration
│   │   └── websocket.py             # WebSocket for real-time job updates
│   ├── services/
│   │   ├── gemini_service.py        # Gemini API integration for image generation
│   │   ├── watermark_service.py     # PyTorch-based watermark removal
│   │   ├── storage_service.py       # Google Cloud Storage management
│   │   └── batch_service.py         # Batch processing orchestration
│   ├── tasks/
│   │   ├── localization_tasks.py    # Celery tasks for background processing
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── localization.py          # Pydantic models (request/response schemas)
│   ├── models/
│   │   ├── __init__.py
│   │   └── job.py                   # SQLAlchemy models for database
│   └── utils/
│       ├── __init__.py
│       └── prompts.py               # Modular prompt templates with market demographics
├── main.py                          # Entry point (loads env vars, starts uvicorn)
├── entrypoint.sh                    # Docker entrypoint supporting api/worker/both modes
├── Dockerfile                       # Multi-stage Docker build for production
├── docker-compose.yml               # Local development orchestration (Redis, API, Worker)
├── .env.example                     # Environment variable template
├── .env                             # Actual environment variables (git ignored)
├── .dockerignore                    # Files to exclude from Docker build
├── .gitignore                       # Git ignore rules
├── pyproject.toml                   # Project configuration and dependencies
├── uv.lock                          # Locked dependency versions
├── model.pth                        # PyTorch watermark removal model
├── vyloc-479312-3866732f745d.json   # Google Cloud service account credentials
└── README.md                        # This file
```

---

## Setup & Installation

### Prerequisites

- **Python 3.12+** - Required for type hints and async improvements
- **uv** (recommended) - Fast Python package manager (`pip install uv`)
- **Docker & Docker Compose** (optional) - For containerized development/deployment
- **Google Cloud Project** - For Gemini API access and Cloud Storage
- **Supabase Project** - For PostgreSQL database

### Step 1: Clone the Repository

```bash
git clone https://github.com/devesh1011/vyloc-backend-api.git
cd vyloc-backend-api/backend
```

### Step 2: Create Virtual Environment

**Using uv:**

```bash
uv venv
source .venv/bin/activate
```

**Using pip:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

**Using uv:**

```bash
uv pip install -e .
```

**Using pip:**

```bash
pip install -e .
```

### Step 4: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see [Configuration](#configuration) section).

---

## Configuration

### Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
ENV=development
APP_NAME=Vyloc
APP_VERSION=0.1.0

# Google Cloud - Gemini AI
GOOGLE_API_KEY=your_gemini_api_key_here
VERTEX_AI_PROJECT=your_gcp_project_id
VERTEX_AI_LOCATION=global
USE_VERTEX_AI=true
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json  # For Docker/Cloud Run

# Google Cloud Storage
GCS_BUCKET_NAME=vyloc-images
GCS_PROJECT_ID=your_gcp_project_id
GCS_CREDENTIALS_PATH=/path/to/credentials.json  # Local development only

# Supabase Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Redis (for Celery message broker)
REDIS_URL=redis://localhost:6379/0

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,https://yourdomain.com

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Watermark Model
WATERMARK_MODEL_PATH=./model.pth
```

### Key Configuration Explanations

| Variable            | Purpose                                    | Example                             |
| ------------------- | ------------------------------------------ | ----------------------------------- |
| `GOOGLE_API_KEY`    | Gemini API authentication                  | Generated from Google Cloud Console |
| `VERTEX_AI_PROJECT` | GCP project for Vertex AI                  | `vyloc-479312`                      |
| `USE_VERTEX_AI`     | Use Vertex AI (true) or direct API (false) | `true` for production               |
| `GCS_BUCKET_NAME`   | Cloud Storage bucket for images            | `vyloc-images`                      |
| `SUPABASE_URL`      | Database endpoint                          | `https://project.supabase.co`       |
| `REDIS_URL`         | Message broker for background jobs         | `redis://localhost:6379/0`          |
| `CORS_ORIGINS`      | Allowed frontend origins                   | `http://localhost:3000`             |

---

## Running the Server

### Local Development (with auto-reload)

```bash
# Using the dev script
python -m app.main

# Or directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access the API

- **API Documentation (Swagger UI)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **API Root**: http://localhost:8000/

### Production Server

```bash
# Using uvicorn with 4 worker processes
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Using Gunicorn (more stable for production)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

---

## Docker Deployment

### Local Development with Docker Compose

The `docker-compose.yml` orchestrates three services:

1. **Redis** - Message broker for Celery
2. **API** - FastAPI server (port 8000)
3. **Worker** - Celery worker for background jobs

**Start all services:**

```bash
docker-compose up --build
```

**View logs:**

```bash
docker-compose logs -f api       # API logs
docker-compose logs -f worker    # Worker logs
docker-compose logs -f redis     # Redis logs
```

**Stop services:**

```bash
docker-compose down
```

### Production Dockerfile

The `Dockerfile` uses a **multi-stage build** for optimization:

**Stage 1 (Builder):**

- Installs dependencies using `uv`
- Creates optimized virtual environment
- Size: ~3GB (temporarily)

**Stage 2 (Runtime):**

- Copies only the venv from stage 1
- Minimal base dependencies
- Final image: **1.95GB** (optimized with CPU-only PyTorch)

**Key features:**

- Non-root user (`appuser:appgroup`) for security
- `entrypoint.sh` supports flexible service types (api/worker/both)
- Application Default Credentials (ADC) for Cloud Run authentication

**Build the image:**

```bash
docker build -t vyloc-backend:latest .
```

**Run the API:**

```bash
docker run -p 8000:8000 \
  -e SERVICE=api \
  -e GOOGLE_API_KEY=your_key \
  -e VERTEX_AI_PROJECT=your_project \
  vyloc-backend:latest
```

**Run the Worker:**

```bash
docker run \
  -e SERVICE=worker \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  vyloc-backend:latest
```

### Google Cloud Run Deployment

**Deploy API service:**

```bash
gcloud run deploy vyloc-api \
  --source . \
  --service-account vyloc-sa@project.iam.gserviceaccount.com \
  --set-env-vars SERVICE=api \
  --allow-unauthenticated \
  --region us-central1
```

**Deploy Worker service:**

```bash
gcloud run deploy vyloc-worker \
  --source . \
  --service-account vyloc-sa@project.iam.gserviceaccount.com \
  --set-env-vars SERVICE=worker \
  --region us-central1 \
  --no-gen2  # Prevents PORT 8080 timeout issue
```

---

## API Endpoints

### Health & Status

```
GET /health
```

Returns API status and service availability.

**Response:**

```json
{
  "status": "ok",
  "gemini_available": true,
  "storage_available": true,
  "db_available": true
}
```

### Real-Time Localization

```
POST /localize
```

Generate localized images for target languages synchronously.

**Request:**

```json
{
  "image_url": "https://...",
  "target_languages": ["japanese", "korean", "german"],
  "image_size": "2048x2048",
  "aspect_ratio": "1:1"
}
```

**Response:**

```json
{
  "job_id": "20251209054945_6a6225c9",
  "status": "processing",
  "progress": 0,
  "localized_images": [
    {
      "language": "japanese",
      "market": "japan",
      "image_url": "https://storage.googleapis.com/vyloc-images/...",
      "status": "completed",
      "processing_time_ms": 8500
    }
  ]
}
```

### Batch Processing

```
POST /batch/process
```

Cost-effective batch API for 50+ images (50% cheaper than real-time).

**Request:**

```json
{
  "images": [
    {
      "id": "img_001",
      "url": "https://...",
      "target_languages": ["japanese", "korean"]
    }
  ]
}
```

**Response:**

```json
{
  "batch_id": "batch_20251209_xxx",
  "status": "queued",
  "total_images": 50,
  "estimated_completion": "2025-12-09T10:30:00Z"
}
```

### WebSocket Real-Time Updates

```
WS /ws/job/{job_id}
```

Connect to receive real-time job status updates.

**Message format:**

```json
{
  "job_id": "20251209054945_6a6225c9",
  "status": "processing",
  "progress": 45,
  "message": "Processing Japanese version..."
}
```

### Payment Integration

```
POST /payments/create-checkout
```

Create Stripe checkout session for credit purchases.

```
POST /payments/webhook
```

Stripe webhook for payment confirmation.

---

## Database Schema

### Jobs Table

Stores localization job metadata and results.

```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  job_id TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'processing',
  progress INTEGER DEFAULT 0,
  original_image_url TEXT,
  target_languages TEXT[] NOT NULL,
  localized_images JSONB,
  processing_time_ms INTEGER,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Usage Table

Tracks credit usage per user.

```sql
CREATE TABLE usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  credits_used INTEGER NOT NULL,
  job_id UUID REFERENCES jobs(id),
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Credits Table

Tracks user credit balance.

```sql
CREATE TABLE user_credits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id),
  total_credits INTEGER DEFAULT 100,
  used_credits INTEGER DEFAULT 0,
  available_credits INTEGER GENERATED ALWAYS AS (total_credits - used_credits) STORED,
  updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Background Jobs

### Celery Worker Setup

Background tasks are handled by **Celery with Redis** as the message broker.

**Start Celery Worker:**

```bash
celery -A app.tasks.localization_tasks worker --loglevel=info
```

**Or with docker-compose:**

```bash
docker-compose up
```

### Available Tasks

**`process_localization`** - Main image localization task

- Generates localized images for target languages
- Uploads results to Cloud Storage
- Updates job status in database
- Handles watermark removal post-processing

**`process_batch`** - Batch processing orchestrator

- Queues multiple images for processing
- Tracks batch progress
- Generates cost summary

**Typical Flow:**

1. Frontend sends image to `/localize` endpoint
2. API creates job record in database
3. Background task starts processing immediately
4. WebSocket sends real-time updates to client
5. Results stored in Cloud Storage upon completion
6. Job marked as completed in database

---

## Architecture

### Request Flow

```
Frontend (Next.js)
    ↓
API (FastAPI)
    ↓ (1. Create job, 2. Queue task)
Redis (Message Broker)
    ↓
Celery Worker
    ├─ Gemini Service (Image Generation)
    ├─ Watermark Service (Inpainting)
    └─ Storage Service (GCS Upload)
    ↓
Supabase (Job Status Update)
    ↓
WebSocket (Real-time Update to Frontend)
```

### Parallel Processing

**Image Generation Phase:**

```python
# All language versions generated in parallel
tasks = [
  gemini_service.localize_image(image, 'japanese'),
  gemini_service.localize_image(image, 'korean'),
  gemini_service.localize_image(image, 'german'),
]
results = await asyncio.gather(*tasks)  # Concurrent execution
```

**Post-Processing Phase:**

```python
# Watermark removal + Cloud Storage upload in parallel
post_process_tasks = [
  watermark_service.remove(image_1),
  storage_service.upload(image_2),
  ...
]
await asyncio.gather(*post_process_tasks)
```

### Error Handling

- **Retry Logic**: Failed API calls retry with exponential backoff
- **Timeout Protection**: 2-minute timeout for Gemini requests
- **Graceful Degradation**: If watermark removal fails, upload original
- **User Feedback**: Detailed error messages in job status

---

## Development

### Adding New Endpoints

1. Create router in `app/routers/`:

```python
# app/routers/newfeature.py
from fastapi import APIRouter

router = APIRouter(prefix="/newfeature", tags=["Feature"])

@router.post("/endpoint")
async def new_endpoint():
    return {"status": "ok"}
```

2. Register in `app/main.py`:

```python
from app.routers import newfeature
app.include_router(newfeature.router)
```

### Adding New Services

1. Create service in `app/services/`:

```python
# app/services/myservice.py
class MyService:
    def __init__(self):
        self.is_available = True

    async def process(self, data):
        # Implementation
        pass

def get_my_service() -> MyService:
    return MyService()
```

2. Use in endpoints:

```python
from app.services.myservice import get_my_service

service = get_my_service()
result = await service.process(data)
```

### Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=app tests/
```

### Code Quality

```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

---

## Troubleshooting

### Gemini API Not Initialized

**Problem:** `⚠️ Gemini AI service not available - check GOOGLE_API_KEY`

**Solution:**

1. Verify `GOOGLE_API_KEY` in `.env`
2. Check Google Cloud Console for valid API key
3. Ensure Gemini API is enabled in your project
4. For Vertex AI, verify service account has `aiplatform.endpoints.predict` permission

### Database Connection Failed

**Problem:** `Error: could not connect to server`

**Solution:**

1. Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
2. Check database is running
3. Test connection: `curl https://your-supabase-url/rest/v1/jobs`

### Redis Connection Failed

**Problem:** `Error: cannot connect to Redis`

**Solution:**

1. Verify Redis is running: `redis-cli ping`
2. Check `REDIS_URL` format: `redis://localhost:6379/0`
3. For Docker: ensure Redis container is healthy

### Worker Not Processing Tasks

**Problem:** Jobs stuck in "processing" state

**Solution:**

```bash
# Check worker logs
docker-compose logs worker

# Verify Redis has tasks
redis-cli LLEN celery

# Restart worker
docker-compose restart worker
```

### Watermark Removal Failing

**Problem:** `model.pth not found`

**Solution:**

1. Ensure `model.pth` is in backend root directory
2. For Docker, verify file is copied: `docker exec <container> ls -lh /app/model.pth`
3. Check file permissions: `chmod 644 model.pth`

### GCS Upload Failing

**Problem:** `Permission denied` on Cloud Storage

**Solution:**

1. Verify service account has `storage.admin` role
2. Check `GCS_BUCKET_NAME` matches actual bucket
3. For Cloud Run, ensure `GOOGLE_APPLICATION_CREDENTIALS` is set correctly

---

## Performance Metrics

- **Image Generation**: 8-12 seconds per language (Gemini 3 Pro Image)
- **Watermark Removal**: 2-3 seconds per image (PyTorch inpainting)
- **GCS Upload**: 1-2 seconds per image (depending on file size)
- **Total Processing**: ~20 seconds for 3 languages (parallel execution)
- **Throughput**: Supports 100+ concurrent jobs with proper scaling
