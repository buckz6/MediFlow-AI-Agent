import os
from pathlib import Path

import httpx
import pytest


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(path: Path):
    return path.open("rb")


def assert_base_response(response: httpx.Response):
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert set(
        [
            "diagnosis",
            "confidence",
            "findings",
            "heatmap_base64",
            "clinical_summary",
            "finance_estimate",
            "patient_education",
            "processing_time_ms",
        ]
    ).issubset(body.keys())
    assert isinstance(body["confidence"], float)
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["heatmap_base64"], str)
    assert body["heatmap_base64"].startswith("data:image/png;base64,")
    assert isinstance(body["processing_time_ms"], (int, float))
    assert body["processing_time_ms"] < 30000
    assert isinstance(body["finance_estimate"], dict)
    assert set(["total_idr", "bpjs_covered"]).issubset(body["finance_estimate"].keys())
    return body


def test_health(base_url: str):
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert body.get("model_loaded") is True


def test_analyze_normal_xray(base_url: str):
    normal_path = FIXTURE_DIR / "sample_xray_normal.png"
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        with read_fixture(normal_path) as f:
            files = {"xray_image": (normal_path.name, f, "image/png")}
            response = client.post("/api/analyze", files=files)

    body = assert_base_response(response)
    assert isinstance(body["findings"], list)


def test_analyze_abnormal_xray(base_url: str):
    abnormal_path = FIXTURE_DIR / "sample_xray_abnormal.png"
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        with read_fixture(abnormal_path) as f:
            files = {"xray_image": (abnormal_path.name, f, "image/png")}
            data = {"patient_notes": "Batuk 3 minggu, berkeringat malam"}
            response = client.post("/api/analyze", files=files, data=data)

    body = assert_base_response(response)
    assert isinstance(body["findings"], list)
    assert len(body["findings"]) >= 1
    assert isinstance(body["patient_education"], str)
    assert body["patient_education"].strip() != ""


def test_invalid_file_type(base_url: str):
    this_file = Path(__file__).resolve()
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        with this_file.open("rb") as f:
            files = {"xray_image": (this_file.name, f, "text/x-python")}
            response = client.post("/api/analyze", files=files)

    assert response.status_code == 400
    body = response.json()
    if isinstance(body, dict) and "detail" in body:
        assert body["detail"].get("code") == "INVALID_FILE_TYPE"
    else:
        assert body.get("code") == "INVALID_FILE_TYPE"


def test_missing_xray(base_url: str):
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        response = client.post("/api/analyze", data={"patient_notes": "only notes, no image"})

    assert response.status_code == 422


def test_performance(base_url: str):
    normal_path = FIXTURE_DIR / "sample_xray_normal.png"
    timings = []

    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        for _ in range(3):
            with read_fixture(normal_path) as f:
                files = {"xray_image": (normal_path.name, f, "image/png")}
                response = client.post("/api/analyze", files=files)
            assert response.status_code == 200
            body = response.json()
            assert "processing_time_ms" in body
            timings.append(float(body["processing_time_ms"]))

    avg = sum(timings) / len(timings)
    minimum = min(timings)
    maximum = max(timings)
    print(f"Average: {avg:.2f}ms | Min: {minimum:.2f}ms | Max: {maximum:.2f}ms")
    assert avg < 25000
