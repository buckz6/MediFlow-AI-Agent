"""
clinical_summarizer.py
──────────────────────
Summarizes doctor-patient transcripts via Gemini with three resilience layers:

  1. Exponential backoff  — retries up to 3× on 429 / quota errors
  2. Model fallback       — gemini-1.5-pro → gemini-1.5-flash on sustained failure
  3. LRU response cache   — skips API call for identical transcripts (max 128 entries)
"""

import functools
import hashlib
import logging
import os
import random
import time
from collections import OrderedDict
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

import google.genai as genai
from google.genai import types as genai_types

from .consultation_transcriber import TranscriptTurn

logger = logging.getLogger(__name__)

# ── Model priority list ───────────────────────────────────────────────────────
_MODELS_PRIORITY = ["gemini-1.5-pro", "gemini-1.5-flash"]
_MAX_OUTPUT_TOKENS = 1024

# ── LRU cache (bounded at 128 entries to prevent memory leak on 4 GB VM) ─────
_CACHE_MAX = 128
_cache: OrderedDict[str, str] = OrderedDict()


def _cache_get(key: str) -> str | None:
    if key not in _cache:
        return None
    # Move to end = most recently used
    _cache.move_to_end(key)
    return _cache[key]


def _cache_set(key: str, value: str) -> None:
    if key in _cache:
        _cache.move_to_end(key)
    else:
        if len(_cache) >= _CACHE_MAX:
            # Evict least recently used (first item)
            evicted = next(iter(_cache))
            del _cache[evicted]
            logger.debug("LRU cache evicted oldest entry (size=%d)", _CACHE_MAX)
    _cache[key] = value


def _content_key(text: str) -> str:
    """SHA-256 hex digest of the prompt text — used as cache key."""
    return hashlib.sha256(text.encode()).hexdigest()


# ── Exponential backoff decorator ─────────────────────────────────────────────

P = ParamSpec("P")
R = TypeVar("R")


def gemini_retry(max_attempts: int = 3) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Retries the decorated function up to `max_attempts` times on Gemini
    rate-limit (429) or quota errors, using exponential backoff + jitter.
    All other exceptions propagate immediately.
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    err = str(exc).lower()
                    is_rate_limit = "429" in err or "quota" in err or "resource_exhausted" in err
                    if is_rate_limit and attempt < max_attempts - 1:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        # Log attempt count only — never log exc message (may contain key in URL)
                        logger.warning(
                            "Gemini rate limit hit — retry %d/%d in %.1fs",
                            attempt + 1, max_attempts, wait,
                        )
                        time.sleep(wait)
                    else:
                        raise
            # Unreachable, but satisfies type checker
            raise RuntimeError("gemini_retry: exhausted attempts")
        return wrapper  # type: ignore[return-value]
    return decorator


# ── Gemini call with per-model retry + fallback ───────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY is not set.")
    return key


def _call_model(model_name: str, prompt: str) -> str:
    """Single model call — decorated with retry at the call site."""
    client = genai.Client(api_key=_get_api_key())
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=genai_types.GenerateContentConfig(max_output_tokens=_MAX_OUTPUT_TOKENS),
    )
    return response.text


@gemini_retry(max_attempts=3)
def _call_pro(prompt: str) -> str:
    return _call_model("gemini-1.5-pro", prompt)


@gemini_retry(max_attempts=3)
def _call_flash(prompt: str) -> str:
    return _call_model("gemini-1.5-flash", prompt)


def _call_with_fallback(prompt: str) -> str:
    """
    Tries gemini-1.5-pro (3 attempts with backoff).
    If all 3 fail due to rate limits, falls back to gemini-1.5-flash (3 more attempts).
    Any non-rate-limit exception propagates immediately from either model.
    """
    for model_fn, model_name in [(_call_pro, "gemini-1.5-pro"), (_call_flash, "gemini-1.5-flash")]:
        try:
            result = model_fn(prompt)
            if model_name != "gemini-1.5-pro":
                logger.info("Gemini fallback: used %s for this request", model_name)
            return result
        except Exception as exc:
            err = str(exc).lower()
            is_rate_limit = "429" in err or "quota" in err or "resource_exhausted" in err
            if is_rate_limit and model_fn is _call_pro:
                logger.warning("gemini-1.5-pro exhausted all retries — falling back to flash")
                continue
            raise

    raise RuntimeError("All Gemini models exhausted after retries and fallback.")


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_transcript_prompt(turns: list[TranscriptTurn]) -> str:
    dialogue = "\n".join(f"{t.speaker}: {t.text}" for t in turns)
    return (
        "You are a clinical documentation assistant. "
        "Summarize the following doctor-patient consultation into: "
        "Chief Complaint, History, Assessment, and Plan.\n\n"
        f"TRANSCRIPT:\n{dialogue}\n\nCLINICAL SUMMARY:"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def summarize_consultation(turns: list[TranscriptTurn]) -> str:
    """
    Summarizes a diarized consultation transcript using Gemini.

    Resilience stack applied in order:
      1. Cache hit  → return immediately, no API call
      2. Pro model  → up to 3 retries with exponential backoff
      3. Flash model → up to 3 retries with exponential backoff (if Pro exhausted)
    """
    prompt = _build_transcript_prompt(turns)
    cache_key = _content_key(prompt)

    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("Gemini cache hit (key=%.8s…)", cache_key)
        return cached

    result = _call_with_fallback(prompt)
    _cache_set(cache_key, result)
    return result
