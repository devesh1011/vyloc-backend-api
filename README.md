# Vyloc Backend API

AI-Powered Product Localization Platform - Backend Service

## Overview

Vyloc enables businesses to seamlessly adapt their product ad images for global markets. This backend service provides:

- **Parallel Image Localization** - Process multiple languages simultaneously
- **Cultural Adaptation** - Adapt visual elements for target markets
- **Demographic Representation** - Modify people in images to match target demographics
- **Watermark Removal** - AI-based inpainting to remove generated watermarks

## Tech Stack

- **FastAPI** - High-performance async Python web framework
- **Pydantic** - Data validation and settings management
- **Google GenAI SDK** - Gemini API for image generation
- **OpenCV** - AI-based watermark removal via inpainting
- **Google Cloud Storage** - Image storage and delivery

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── core/
│   │   └── config.py           # Settings and configuration
│   ├── routers/
│   │   └── localization.py     # Localization API endpoints
│   ├── services/
│   │   ├── gemini_service.py   # Gemini AI integration
│   │   ├── watermark_service.py # OpenCV watermark removal
│   │   └── storage_service.py  # GCS storage management
│   ├── schemas/
│   │   └── localization.py     # Pydantic models
│   └── utils/
│       └── prompts.py          # Modular prompt templates
├── .env.example
├── pyproject.toml
└── README.md
```

## Setup

### Prerequisites
- Python 3.12+
- uv package manager (recommended) or pip

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Running the Server

Start the development server:
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc

## Project Structure

```
backend/
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
├── .env.example        # Example environment variables
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with API info

## Next Steps

- Add routers for ad localization endpoints
- Integrate with image processing services
- Add database models
- Implement authentication
- Add API validation and error handling

## Development

For local development, the server runs in reload mode automatically detecting changes to files.

## Deployment

For production deployment:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or use a production ASGI server like Gunicorn:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```
