"""Speech to text.

Only needed if you are starting from audio. If your voice platform already gives you a transcript
with timings (LiveKit, Vapi and Twilio all do), skip this entirely: the eval works on transcripts.

Groq's whisper-large-v3 is the free option and the reason this file is three lines of real code.
"""

from __future__ import annotations

from typing import Protocol


class STT(Protocol):
    def transcribe(self, audio_path: str) -> str: ...


class FakeSTT:
    """Scripted, for tests. Lets you simulate a mis-hearing deliberately."""

    def __init__(self, response: str) -> None:
        self._response = response

    def transcribe(self, audio_path: str) -> str:  # noqa: ARG002
        return self._response


class GroqSTT:
    """Groq whisper-large-v3. Free tier. Needs GROQ_API_KEY.

    NOT exercised by the test suite: it needs a key and a network, and the thing worth testing here
    is the eval logic, not whether Groq's SDK works.
    """

    def __init__(self, api_key: str, model: str = "whisper-large-v3") -> None:
        self._api_key = api_key
        self._model = model

    def transcribe(self, audio_path: str) -> str:
        from groq import Groq

        client = Groq(api_key=self._api_key)
        with open(audio_path, "rb") as fh:
            resp = client.audio.transcriptions.create(file=fh, model=self._model)
        return resp.text
