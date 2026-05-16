import asyncio
import os
from dataclasses import dataclass, field
from typing import AsyncIterator

from speechmatics.models import (
    AudioSettings,
    ConnectionSettings,
    TranscriptionConfig,
)
from speechmatics.client import WebsocketClient


@dataclass
class TranscriptTurn:
    speaker: str  # "Doctor" or "Patient"
    text: str


@dataclass
class ConsultationTranscriber:
    """Streams audio bytes to Speechmatics and yields diarized transcript turns."""

    _api_key: str = field(init=False)
    _turns: list[TranscriptTurn] = field(default_factory=list, init=False)

    def __post_init__(self):
        api_key = os.environ.get("SPEECHMATICS_API_KEY")
        if not api_key:
            raise EnvironmentError("SPEECHMATICS_API_KEY is not set.")
        self._api_key = api_key

    def _label_speaker(self, speaker_tag: str) -> str:
        """Maps Speechmatics speaker tags (S1, S2…) to clinical roles."""
        return "Doctor" if speaker_tag == "S1" else "Patient"

    async def transcribe(self, audio_chunks: AsyncIterator[bytes]) -> list[TranscriptTurn]:
        settings = ConnectionSettings(
            url="wss://eu2.rt.speechmatics.com/v2",
            auth_token=self._api_key,
        )
        audio_settings = AudioSettings(encoding="pcm_f32le", sample_rate=16_000, chunk_size=1024)
        config = TranscriptionConfig(
            language="en",
            enable_partials=False,
            diarization="speaker",
            speaker_diarization_config={"max_speakers": 2},
        )

        client = WebsocketClient(settings)
        turns: list[TranscriptTurn] = []

        def on_final_transcript(msg: dict):
            for result in msg.get("results", []):
                text = result.get("alternatives", [{}])[0].get("content", "").strip()
                speaker_tag = result.get("alternatives", [{}])[0].get("speaker", "S2")
                if text:
                    turns.append(TranscriptTurn(self._label_speaker(speaker_tag), text))

        client.add_event_handler("AddTranscript", on_final_transcript)

        async def audio_generator():
            async for chunk in audio_chunks:
                yield chunk

        await client.run(audio_generator(), config, audio_settings)
        self._turns = turns
        return turns
