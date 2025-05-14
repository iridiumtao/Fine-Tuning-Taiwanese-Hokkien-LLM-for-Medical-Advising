"""
Simple latency & throughput benchmark for /generate endpoint.
Run:  python benchmark_generate.py
"""

import requests
import time
import uuid
from datetime import datetime, timezone
import numpy as np

FASTAPI_URL = "http://localhost:8000/generate"
NUM_REQUESTS = 100
TEMPERATURE = 0.7
TOP_P = 0.95
PROMPT = "頭殼痛"  # Taigi for “headache”

inference_times = []

for _ in range(NUM_REQUESTS):
    payload = {
        "prompt": PROMPT,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "session_id": str(uuid.uuid4()),  # unique per request
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    start = time.perf_counter()
    response = requests.post(FASTAPI_URL, json=payload)
    duration = time.perf_counter() - start

    if response.status_code == 200:
        inference_times.append(duration)
    else:
        print(f"[ERROR] {response.status_code}: {response.text}")

# ───── Metrics ─────
inference_times = np.array(inference_times)

if len(inference_times) == 0:
    print("No successful responses recorded.")
else:
    median_ms = np.median(inference_times) * 1000  # seconds→ms
    p95_ms = np.percentile(inference_times, 95) * 1000
    p99_ms = np.percentile(inference_times, 99) * 1000
    throughput = len(inference_times) / inference_times.sum()

    print(f"Total successful requests : {len(inference_times)}/{NUM_REQUESTS}")
    print(f"Median latency            : {median_ms:.2f} ms")
    print(f"95th‑percentile latency   : {p95_ms:.2f} ms")
    print(f"99th‑percentile latency   : {p99_ms:.2f} ms")
    print(f"Throughput                : {throughput:.2f} req/s")
