import asyncio
import json
import logging
import os
import time

import google.generativeai as genai
import httpx

logger = logging.getLogger(__name__)

_SPEECHMATICS_BASE = "https://asr.api.speechmatics.com/v2/jobs"
_SUPPORTED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
_POLL_INTERVAL = 3   # seconds
_POLL_TIMEOUT = 120  # seconds

_JOB_CONFIG = {
    "type": "transcription",
    "transcription_config": {
        "language": "id",
        "diarization": "speaker",
        "operating_point": "enhanced",
    },
}

_SPEAKER_LABELS = {"S1": "Dokter", "S2": "Pasien"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def transcribe_audio(audio_path: str) -> dict:
    """
    Full pipeline: Speechmatics transcription + Gemini clinical extraction.

    Returns:
        {
            "transcript": {"raw_transcript": str, "speakers": list, "duration_seconds": float},
            "clinical_extraction": {"chief_complaint": str, "symptoms": list,
                                    "medical_history": list, "doctor_recommendation": str}
        }
        or {"error": "transcription_failed", "transcript": None} on Speechmatics failure.
    """
    _validate_file(audio_path)

    api_key = os.environ.get("SPEECHMATICS_API_KEY", "")
    if not api_key:
        logger.error("SPEECHMATICS_API_KEY is not set")
        return {"error": "transcription_failed", "transcript": None}

    try:
        job_id = await _submit_job(audio_path, api_key)
        transcript_json = await _poll_until_done(job_id, api_key)
    except _TranscriptionError as exc:
        logger.error("Speechmatics error: %s", exc)
        return {"error": "transcription_failed", "transcript": None}

    transcript = _parse_transcript(transcript_json)
    clinical = await _extract_clinical(transcript["raw_transcript"])

    return {"transcript": transcript, "clinical_extraction": clinical}


# Keep backward-compat alias used by main.py
transcribe_consultation = transcribe_audio


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _TranscriptionError(Exception):
    pass


def _validate_file(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext not in _SUPPORTED_EXT:
        raise _TranscriptionError(f"Unsupported format '{ext}'. Allowed: {_SUPPORTED_EXT}")
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise _TranscriptionError(f"Cannot access file: {exc}") from exc
    if size > _MAX_FILE_BYTES:
        raise _TranscriptionError(f"File {size / 1024 / 1024:.1f} MB exceeds 50 MB limit")


async def _submit_job(audio_path: str, api_key: str) -> str:
    """Upload audio and return job_id."""
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(audio_path, "rb") as fh:
        audio_bytes = fh.read()

    filename = os.path.basename(audio_path)
    files = {
        "data_file": (filename, audio_bytes, "application/octet-stream"),
        "config": (None, json.dumps(_JOB_CONFIG), "application/json"),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(_SPEECHMATICS_BASE + "/", headers=headers, files=files)
    except httpx.RequestError as exc:
        raise _TranscriptionError(f"Network error on submit: {exc}") from exc

    if resp.status_code not in (200, 201):
        raise _TranscriptionError(f"Submit failed [{resp.status_code}]: {resp.text[:200]}")

    return resp.json()["id"]


async def _poll_until_done(job_id: str, api_key: str) -> dict:
    """Poll job status every 3 s, then fetch transcript. Max wait 120 s."""
    status_url = f"{_SPEECHMATICS_BASE}/{job_id}/"
    transcript_url = f"{_SPEECHMATICS_BASE}/{job_id}/transcript"
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.monotonic() + _POLL_TIMEOUT

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while time.monotonic() < deadline:
                resp = await client.get(status_url, headers=headers)
                if resp.status_code != 200:
                    raise _TranscriptionError(f"Status poll failed [{resp.status_code}]")

                job = resp.json().get("job", {})
                status = job.get("status", "")

                if status == "done":
                    tr = await client.get(transcript_url, headers=headers, params={"format": "json-v2"})
                    if tr.status_code != 200:
                        raise _TranscriptionError(f"Transcript fetch failed [{tr.status_code}]")
                    return tr.json()

                if status in ("rejected", "deleted"):
                    raise _TranscriptionError(f"Job ended with status '{status}'")

                await asyncio.sleep(_POLL_INTERVAL)

    except httpx.RequestError as exc:
        raise _TranscriptionError(f"Network error while polling: {exc}") from exc

    raise _TranscriptionError(f"Job did not complete within {_POLL_TIMEOUT} seconds")


def _parse_transcript(data: dict) -> dict:
    """
    Parse Speechmatics json-v2 response.

    json-v2 structure:
      {"results": [{"type": "word"|"punctuation",
                    "alternatives": [{"content": str, "speaker": "S1"|"S2", ...}],
                    "end_time": float}, ...]}
    """
    speaker_words: dict[str, list[str]] = {}
    all_words: list[str] = []
    duration = 0.0

    for result in data.get("results", []):
        alt = result.get("alternatives", [{}])[0]
        content = alt.get("content", "").strip()
        speaker_tag = alt.get("speaker", "S1")
        result_type = result.get("type", "word")

        if not content:
            continue

        duration = max(duration, result.get("end_time", 0.0))

        if result_type == "punctuation":
            # Attach punctuation to previous word without space
            if all_words:
                all_words[-1] += content
            if speaker_tag in speaker_words and speaker_words[speaker_tag]:
                speaker_words[speaker_tag][-1] += content
            continue

        speaker_words.setdefault(speaker_tag, []).append(content)
        all_words.append(content)

    speakers = [
        {
            "speaker": _SPEAKER_LABELS.get(tag, tag),
            "text": " ".join(words),
        }
        for tag, words in sorted(speaker_words.items())
    ]

    return {
        "raw_transcript": " ".join(all_words),
        "speakers": speakers,
        "duration_seconds": round(duration, 2),
    }


async def _extract_clinical(transcript_text: str) -> dict:
    """Send transcript to Gemini 1.5 Pro for structured clinical extraction."""
    _FALLBACK = {
        "chief_complaint": "",
        "symptoms": [],
        "medical_history": [],
        "doctor_recommendation": "",
    }

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        logger.warning("GEMINI_API_KEY not set — skipping clinical extraction")
        return _FALLBACK

    prompt = (
        "Dari transkrip konsultasi dokter-pasien berikut, ekstrak dalam JSON:\n"
        "{\n"
        "  'chief_complaint': 'keluhan utama pasien',\n"
        "  'symptoms': ['gejala 1', 'gejala 2'],\n"
        "  'medical_history': ['riwayat 1'],\n"
        "  'doctor_recommendation': 'rekomendasi dokter'\n"
        "}\n"
        f"Transkrip: {transcript_text}"
    )

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(
            "gemini-1.5-pro",
            generation_config=genai.GenerationConfig(max_output_tokens=1024),
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if present
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()

        result = json.loads(raw)
        return {
            "chief_complaint": result.get("chief_complaint", ""),
            "symptoms": result.get("symptoms", []),
            "medical_history": result.get("medical_history", []),
            "doctor_recommendation": result.get("doctor_recommendation", ""),
        }

    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON clinical extraction")
        return _FALLBACK
    except Exception as exc:
        logger.warning("Clinical extraction failed: %s", type(exc).__name__)
        return _FALLBACK
