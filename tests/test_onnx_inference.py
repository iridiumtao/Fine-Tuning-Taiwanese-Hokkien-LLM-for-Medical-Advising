"""
PyTest suite for ONNX model validation & benchmarking.

Run:  pytest -q tests/test_onnx_inference.py
"""

import os
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pytest
import torch


@pytest.fixture(scope="session")
def ort_session(onnx_model_path: Path) -> ort.InferenceSession:
    """
    Create an ONNX Runtime inference session with GPU only.
    Fail the test suite immediately if CUDAExecutionProvider is unavailable.
    """
    # Check if GPU provider is available
    available_providers = ort.get_available_providers()
    if "CUDAExecutionProvider" not in available_providers:
        pytest.fail("CUDAExecutionProvider (GPU) not available. Aborting tests.")

    # Only use GPU provider
    session = ort.InferenceSession(
        str(onnx_model_path),
        providers=["CUDAExecutionProvider"]
    )
    yield session

    # explicit session release
    session._sess = None

@pytest.fixture(scope="session")
def onnx_model_path() -> Path:
    path = Path(os.getenv("ONNX_MODEL_PATH", "models/stage2.onnx"))
    if not path.exists():
        pytest.skip(f"ONNX model not found: {path}")
    return path


def _infer(session: ort.InferenceSession, inputs: np.ndarray) -> np.ndarray:
    """Run forward pass and return raw logits."""
    ort_inputs = {session.get_inputs()[0].name: inputs}
    return session.run(None, ort_inputs)[0]


# =========================
# Tests & Benchmarks
# =========================
def test_model_size(onnx_model_path: Path):
    """Ensure model file is not unexpectedly bloated."""
    size_mb = onnx_model_path.stat().st_size / 1e6
    print(f"\nModel size on disk: {size_mb:.2f} MB")
    assert size_mb < 50000, "ONNX model is larger than 100 MB (adjust threshold if needed)"


def test_accuracy(ort_session, test_loader):
    # todo:
    pass
    assert acc > 50, "Accuracy below expected threshold"


@pytest.mark.performance
def test_single_sample_latency(ort_session, test_loader):
    """Measure median / P95 / P99 latency for single‑sample inference."""
    sample, _ = next(iter(test_loader))
    sample = sample[:1].numpy()

    # Warm‑up
    _ = _infer(ort_session, sample)

    n_trials = 100
    times = []
    for _ in range(n_trials):
        t0 = time.time()
        _ = _infer(ort_session, sample)
        times.append(time.time() - t0)

    med, p95, p99 = np.percentile(times, [50, 95, 99]) * 1000  # ms
    print(f"\nLatency (ms) – median: {med:.2f}, P95: {p95:.2f}, P99: {p99:.2f}")
    # Example thresholds – tune for your hardware
    assert med < 500, "Median latency too high"


@pytest.mark.performance
def test_batch_throughput(ort_session, test_loader):
    """Compute FPS throughput for one batch over multiple runs."""
    batch, _ = next(iter(test_loader))
    batch_np = batch.numpy()

    # Warm‑up
    _ = _infer(ort_session, batch_np)

    n_batches = 50
    times = []
    for _ in range(n_batches):
        t0 = time.time()
        _ = _infer(ort_session, batch_np)
        times.append(time.time() - t0)

    fps = (batch_np.shape[0] * n_batches) / np.sum(times)
    print(f"\nBatch throughput: {fps:.2f} FPS")
    assert fps > 200, "Throughput below expected threshold"