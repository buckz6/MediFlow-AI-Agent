"""
Health check untuk MediFlow backend.
Dijalankan oleh Docker sebagai: python health_check.py
Exit 0 = sehat, Exit 1 = tidak sehat.

Memeriksa:
  1. FastAPI root endpoint responsif
  2. GEMINI_API_KEY tersedia dan Gemini API dapat dijangkau
  3. SPEECHMATICS_API_KEY tersedia dan endpoint Speechmatics dapat dijangkau
"""

import os
import sys

import httpx


def check_fastapi() -> bool:
    try:
        r = httpx.get("http://localhost:8000/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def check_gemini() -> bool:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        # Jangan print key — hanya status (fix CWE-200)
        print("HEALTH_CHECK FAIL: GEMINI_API_KEY tidak di-set", file=sys.stderr)
        return False
    try:
        r = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=8,
        )
        if r.status_code == 403:
            print("HEALTH_CHECK FAIL: GEMINI_API_KEY tidak valid (HTTP 403)", file=sys.stderr)
            return False
        return True
    except Exception:
        # Jangan log exception message — bisa mengandung URL dengan key (fix CWE-200)
        print("HEALTH_CHECK FAIL: Gemini tidak dapat dijangkau", file=sys.stderr)
        return False


def check_speechmatics() -> bool:
    api_key = os.environ.get("SPEECHMATICS_API_KEY", "")
    if not api_key:
        print("HEALTH_CHECK FAIL: SPEECHMATICS_API_KEY tidak di-set", file=sys.stderr)
        return False
    try:
        r = httpx.get(
            "https://mp.speechmatics.com/v1/api_keys",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8,
        )
        if r.status_code in (401, 403):
            print(f"HEALTH_CHECK FAIL: Speechmatics API key tidak valid (HTTP {r.status_code})", file=sys.stderr)
            return False
        return True
    except Exception:
        # Jangan log exception message — bisa mengandung header Authorization (fix CWE-200)
        print("HEALTH_CHECK FAIL: Speechmatics tidak dapat dijangkau", file=sys.stderr)
        return False


if __name__ == "__main__":
    results = {
        "fastapi":      check_fastapi(),
        "gemini":       check_gemini(),
        "speechmatics": check_speechmatics(),
    }

    for service, ok in results.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {service}")

    sys.exit(0 if all(results.values()) else 1)
