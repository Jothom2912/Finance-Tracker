import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import pika
import requests

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = os.getenv("QUEUE_NAME", "serverless.health.requests")
SERVICE_HEALTH_URLS = [
    url.strip()
    for url in os.getenv(
        "SERVICE_HEALTH_URLS",
        "http://user-service:8001/health,"
        "http://transaction-service:8002/health,"
        "http://account-service:8003/health,"
        "http://categorization-service:8005/health,"
        "http://budget-service:8003/health,"
        "http://goal-service:8006/health,"
        "http://monolith:8000/health",
    ).split(",")
    if url.strip()
]
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))


def _connect_with_retry(max_attempts: int = 30, delay_seconds: float = 2.0) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Connecting to RabbitMQ attempt={attempt} url={RABBITMQ_URL}", flush=True)
            return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        except Exception as exc:  # noqa: BLE001 - this is a small operational job
            last_error = exc
            print(f"RabbitMQ connection failed: {exc}", flush=True)
            time.sleep(delay_seconds)
    raise RuntimeError(f"Could not connect to RabbitMQ after {max_attempts} attempts") from last_error


def _declare_queue(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.queue_declare(queue=QUEUE_NAME, durable=True)


def init_queue() -> None:
    connection = _connect_with_retry()
    try:
        channel = connection.channel()
        _declare_queue(channel)
        print(json.dumps({"status": "initialized", "queue": QUEUE_NAME}), flush=True)
    finally:
        connection.close()


def publish_messages(count: int = 1) -> None:
    connection = _connect_with_retry()
    try:
        channel = connection.channel()
        _declare_queue(channel)
        for index in range(count):
            payload = {
                "type": "health_report_requested",
                "index": index + 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(payload).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
        print(json.dumps({"status": "published", "queue": QUEUE_NAME, "count": count}), flush=True)
    finally:
        connection.close()


def _check_service(url: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "url": url,
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "elapsed_ms": elapsed_ms,
            "body_preview": response.text[:160],
        }
    except Exception as exc:  # noqa: BLE001 - log any operational failure in report
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "url": url,
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
        }


def run_once() -> int:
    connection = _connect_with_retry()
    try:
        channel = connection.channel()
        _declare_queue(channel)

        method_frame, _header_frame, body = channel.basic_get(queue=QUEUE_NAME, auto_ack=False)
        if method_frame is None:
            print(json.dumps({"status": "no_message", "queue": QUEUE_NAME}), flush=True)
            return 0

        request_payload = json.loads(body.decode("utf-8")) if body else {}
        service_results = [_check_service(url) for url in SERVICE_HEALTH_URLS]
        report = {
            "status": "completed",
            "queue": QUEUE_NAME,
            "request": request_payload,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": len(service_results),
                "healthy": sum(1 for item in service_results if item.get("ok")),
                "unhealthy": sum(1 for item in service_results if not item.get("ok")),
            },
            "services": service_results,
        }

        print(json.dumps(report, indent=2), flush=True)
        channel.basic_ack(method_frame.delivery_tag)
        return 0
    finally:
        connection.close()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "init":
        init_queue()
        return 0
    if mode == "publish":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.getenv("PUBLISH_COUNT", "5"))
        publish_messages(count)
        return 0
    if mode == "run":
        return run_once()

    print(f"Unknown mode: {mode}. Expected one of: init, publish, run", file=sys.stderr, flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
