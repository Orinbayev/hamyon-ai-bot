"""
Speech-to-Text service — Groq Whisper orqali audio matnga o'giradi.
"""

import logging

import aiohttp
from django.conf import settings

logger = logging.getLogger("services")

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"


async def transcribe(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Groq Whisper orqali audio ni o'zbek matnga o'giradi.
    Raises: ValueError (key yo'q), RuntimeError (API xato), Exception (tarmoq xato)
    """
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY sozlanmagan")

    ext = mime_type.split("/")[-1].split(";")[0]  # "ogg", "mp3" ...

    form = aiohttp.FormData()
    form.add_field("file", audio_bytes, filename=f"voice.{ext}", content_type=mime_type)
    form.add_field("model", GROQ_MODEL)
    form.add_field("language", "uz")
    form.add_field("response_format", "text")
    # Kuchli o'zbek moliyaviy lug'at — Whisper turkcha o'rniga o'zbek chiqaradi
    form.add_field("prompt",
        "O'zbekcha moliyaviy xabar: to'ladim, oldim, berdim, sarfladim, ketdi, tushdi, "
        "so'm, ming, million, dollar, rubl, taxi, taksi, ovqat, restoran, kafe, "
        "kiyim, internet, telefon, kommunal, oqish, salomatlik, kino, maosh, qarz, "
        "naqd, karta, Payme, Click, harajat, kirim, chiqim, balans"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=form,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"Groq {resp.status}: {body[:200]}")
            transcript = body.strip()
            logger.debug("Groq transcript: %s", transcript[:120])
            return transcript
