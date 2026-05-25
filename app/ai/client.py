import logging

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger("ai")

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    async def generate(self, prompt: str) -> str:
        for model in [self._model] + FALLBACK_MODELS:
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )
                return response.text or ""
            except Exception as e:
                code = getattr(e, "code", None) or getattr(
                    getattr(e, "status_code", None), "value", None
                )
                if code in (429, 404, 503):
                    logger.warning("Model %s failed (%s), trying next...", model, code)
                    continue
                logger.error("Gemini error: %s", e)
                raise
        raise RuntimeError("Barcha Gemini modellari ishlamayapti.")

    async def generate_with_audio(
        self, audio_bytes: bytes, mime_type: str, prompt: str
    ) -> str:
        for model in [self._model] + FALLBACK_MODELS:
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )
                return response.text or ""
            except Exception as e:
                code = getattr(e, "code", None)
                if code in (429, 404, 503):
                    logger.warning("Audio model %s failed (%s)", model, code)
                    continue
                raise
        raise RuntimeError("Audio uchun Gemini modeli ishlamayapti.")
