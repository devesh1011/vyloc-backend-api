"""
WebSocket router for real-time job status updates.

Provides WebSocket endpoints for clients to receive real-time updates
on localization job progress.
"""

import json
import logging
import asyncio
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# Store active WebSocket connections by job_id
active_connections: Dict[str, Set[WebSocket]] = {}

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class ConnectionManager:
    """Manage WebSocket connections for job updates."""
    
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.redis_client = None
    
    async def get_redis(self):
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(REDIS_URL)
        return self.redis_client
    
    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        if job_id not in self.connections:
            self.connections[job_id] = set()
        self.connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id}")
    
    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        if job_id in self.connections:
            self.connections[job_id].discard(websocket)
            if not self.connections[job_id]:
                del self.connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def send_update(self, job_id: str, data: dict):
        """Send update to all connections for a job."""
        if job_id in self.connections:
            disconnected = set()
            for websocket in self.connections[job_id]:
                try:
                    await websocket.send_json(data)
                except Exception:
                    disconnected.add(websocket)
            
            # Clean up disconnected clients
            for ws in disconnected:
                self.connections[job_id].discard(ws)


manager = ConnectionManager()


async def redis_subscriber(job_id: str, websocket: WebSocket):
    """Subscribe to Redis channel for job updates and forward to WebSocket."""
    try:
        redis_client = await manager.get_redis()
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"job:{job_id}")
        
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                
                # If job is complete, close connection
                if data.get("status") in ["completed", "failed"]:
                    logger.info(f"Job {job_id} finished, closing WebSocket")
                    break
            
            await asyncio.sleep(0.1)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Redis subscriber error for job {job_id}: {e}")
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")


@router.websocket("/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job status updates.
    
    Connect to this endpoint to receive real-time updates on a specific job.
    Updates include progress percentage, status messages, and final results.
    
    Messages are JSON objects with the following structure:
    {
        "job_id": "string",
        "status": "queued" | "processing" | "completed" | "failed",
        "progress": 0-100,
        "message": "string",
        "localized_images": [...],  // Only when completed
        "error": "string"  // Only when failed
    }
    """
    await manager.connect(websocket, job_id)
    
    # Start Redis subscriber task
    subscriber_task = asyncio.create_task(redis_subscriber(job_id, websocket))
    
    try:
        # Send initial status
        await websocket.send_json({
            "job_id": job_id,
            "status": "connected",
            "message": "Connected to job updates",
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message (ping/pong handled automatically)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle client messages if needed
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket, job_id)
