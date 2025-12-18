import json
import random
import logging
import io
from locust import TaskSet, task, between, events
from locust.contrib.fasthttp import FastHttpUser
from PIL import Image

logger = logging.getLogger(__name__)


class LocalizationLoadTest(TaskSet):
    """Task set for localization API endpoints"""

    target_languages = [
        "japanese",
        "korean,german",
        "spanish,french",
        "hindi,chinese_simplified",
    ]

    image_sizes = ["1K", "2K", "4K"]
    user_ids = [
        "f1fba882-c747-42d0-93cd-a316498077b2",  
    ]

    def load_test_image(self):
        """Load the test image from disk."""
        image_path = "wmremove-transformed(2).png"
        try:
            with open(image_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Test image not found: {image_path}")
            img = Image.new("RGB", (800, 600), color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return img_bytes.getvalue()

    @task(3)
    def health_check(self):
        """Health check - lightweight baseline test"""
        self.client.get("/health")

    @task(2)
    def localize_image_async(self):
        """Test async localization endpoint (/api/v1/localize/async)"""
        image_data = self.load_test_image()
        user_id = random.choice(self.user_ids)
        target_langs = random.choice(self.target_languages)
        image_size = random.choice(self.image_sizes)

        with self.client.post(
            "/api/v1/localize/async",
            files={"file": ("test.png", image_data, "image/png")},
            data={
                "target_languages": target_langs,
                "user_id": user_id,
                "image_size": image_size,
                "preserve_faces": "false",
                "remove_watermark": "true",
            },
            catch_response=True,
            timeout=30,
        ) as response:
            if response.status_code in [200, 202]:  
                try:
                    data = response.json()
                    if "job_id" in data and data.get("status") in [
                        "queued",
                        "processing",
                    ]:
                        response.success()
                    else:
                        response.failure(f"Invalid response structure: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 402: 
                response.failure(f"Insufficient credits: {response.text}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")


class VylocAPIUser(FastHttpUser):
    """Simulated user making requests to Vyloc API"""

    tasks = [LocalizationLoadTest]
    wait_time = between(1, 5)  

    def on_start(self):
        """Called when a user starts"""
        pass

    def on_stop(self):
        """Called when a user stops"""
        pass


class WebSocketLoadTest(FastHttpUser):
    """WebSocket connection testing for job updates"""

    wait_time = between(2, 10)

    @task
    def websocket_connection(self):
        """Test WebSocket connection to job updates (/ws/jobs/{job_id})"""
        job_id = "test_job_12345"

        try:
            with self.client.get(
                f"/ws/jobs/{job_id}",
                catch_response=True,
                timeout=10,
            ) as response:
                if response.status_code in [101, 200, 404]:
                    response.success()
                else:
                    response.failure(f"WebSocket failed: {response.status_code}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the load test starts"""
    logger.info("=" * 70)
    logger.info("🚀 Vyloc Backend Load Test Started")
    logger.info(f"Target: {environment.host}")
    logger.info(f"Users: {environment.runner.target_user_count}")
    logger.info("=" * 70)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the load test stops"""
    stats = environment.stats.total
    total_requests = stats.num_requests
    total_failures = stats.num_failures
    success_rate = (
        100 * (total_requests - total_failures) / total_requests
        if total_requests > 0
        else 0
    )

    logger.info("=" * 70)
    logger.info("📊 Load Test Summary")
    logger.info(f"Total requests: {total_requests}")
    logger.info(f"Total failures: {total_failures}")
    logger.info(f"Success rate: {success_rate:.2f}%")
    logger.info(f"Average response time: {stats.avg_response_time:.2f}ms")
    logger.info(f"Max response time: {stats.max_response_time:.2f}ms")
    logger.info("=" * 70)


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    **kwargs,
):
    """Called for every request"""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
    elif response_time > 10000:  # Log slow requests (>10s)
        logger.warning(f"Slow request: {name} took {response_time:.0f}ms")
