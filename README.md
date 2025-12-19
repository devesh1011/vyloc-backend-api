# Vyloc Backend API 🌍

**AI-Powered Product Localization Platform** Automated image adaptation for 15+ global markets using Gemini 3 Pro & PyTorch.

## 🏗️ Architecture & Stack

Vyloc uses an asynchronous, task-based architecture to handle heavy AI image generation.

- **Framework:** FastAPI (Python 3.12+)
- **AI Engine:** Google Gemini 3 Pro (Image Gen) + PyTorch (Inpainting/Watermark Removal)
- **Task Queue:** Celery + Redis (Asynchronous parallel processing)
- **Storage/DB:** Google Cloud Storage & Supabase (PostgreSQL)

---

## 🚀 Quick Start

### 1. Installation

Requires **Python 3.12** and **uv** (recommended).

```bash
git clone https://github.com/devesh1011/vyloc-backend-api.git
cd backend
uv venv && source .venv/bin/activate
uv pip install -e .

```

### 2. Configuration

Create a `.env` file based on `.env.example`. Required keys:

- `GOOGLE_API_KEY`: For Gemini AI.
- `SUPABASE_URL/KEY`: Database access.
- `REDIS_URL`: Task broker.
- `GCS_BUCKET_NAME`: Image storage.

### 3. Execution

**Run via Docker (Recommended):**

```bash
docker-compose up --build

```

**Run Manually:**

```bash
# Terminal 1: API
uvicorn app.main:app --reload
# Terminal 2: Worker
celery -A app.tasks.localization_tasks worker --loglevel=info

```

---

## 📡 Core API Endpoints

| Endpoint         | Method | Description                               |
| ---------------- | ------ | ----------------------------------------- |
| `/localize`      | `POST` | Sync localization for multiple languages. |
| `/batch/process` | `POST` | Queue 50+ images (cost-optimized).        |
| `/ws/job/{id}`   | `WS`   | Real-time status updates via WebSocket.   |
| `/health`        | `GET`  | Service & AI dependency health check.     |

---

## 🛠️ Internal Workflow

1. **Request:** User submits image + target languages.
2. **Queue:** FastAPI creates a DB record and pushes a task to **Redis**.
3. **Process:** **Celery** workers run `asyncio.gather()` to generate all language variants concurrently via Gemini.
4. **Clean:** PyTorch inpainting removes AI artifacts/watermarks.
5. **Store:** Final assets are pushed to **GCS**; **Supabase** is updated.
6. **Notify:** Status is broadcasted to the frontend via **WebSockets**.

---

## 🧪 Development

- **Docs:** View Swagger at `http://localhost:8000/docs`
- **Linting:** `black app/` | `mypy app/`
- **Testing:** `pytest`
