"""
AI Parser — Gemini javobini Pydantic schema orqali validatsiya qiladi.
Noto'g'ri JSON yoki invalid data avtomatik tashlanadi.
"""
import json
import logging
import re
from datetime import date

from app.ai.client import GeminiClient
from app.schemas.transaction import TransactionItem

logger = logging.getLogger("ai.parser")

SYSTEM_PROMPT = """Sen O'zbek tilida yozilgan moliyaviy xabarlarni tahlil qiluvchi AI assistantsan.

Xabardan barcha moliyaviy tranzaksiyalarni JSON massiv sifatida chiqar.

JSON FORMAT (faqat shu formatda javob ber):
[
  {{
    "type": "expense",
    "amount": 45000,
    "currency": "UZS",
    "category": "ovqat",
    "payment_method": "cash",
    "note": "",
    "date": "{today}"
  }}
]

QOIDALAR:
- type: faqat "income" yoki "expense"
- amount: manfiy bo'lmasin, faqat son
- currency: "UZS", "USD" yoki "RUB"
- category: faqat shu qiymatlardan biri:
  ovqat, taxi, transport, kiyim, internet, telefon,
  uy, kommunal, oqish, salomatlik, kongilochar,
  ish_haqi, qarz, sovga, boshqa
- payment_method: cash, card, click, payme, bank, other
- date: ISO format (YYYY-MM-DD), ko'rsatilmagan bo'lsa bugun

MISOLLAR:
"Ovqatga 45 ming ketdi" → [{{"type":"expense","amount":45000,"category":"ovqat",...}}]
"Maosh 3 million tushdi" → [{{"type":"income","amount":3000000,"category":"ish_haqi",...}}]
"Taxiga 20 va ovqatga 30 ming" → ikki element

Moliyaviy ma'lumot bo'lmasa: []

Faqat JSON massiv chiqar, boshqa hech narsa yozma."""


class AIParser:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def parse_text(self, text: str) -> list[TransactionItem]:
        prompt = SYSTEM_PROMPT.format(today=date.today().isoformat()) + f"\n\nXabar: {text}"
        raw = await self.client.generate(prompt)
        return self._validate(raw)

    async def parse_voice(self, audio_bytes: bytes, mime_type: str) -> list[TransactionItem]:
        prompt = SYSTEM_PROMPT.format(today=date.today().isoformat())
        raw = await self.client.generate_with_audio(audio_bytes, mime_type, prompt)
        return self._validate(raw)

    def _validate(self, raw: str) -> list[TransactionItem]:
        """JSON parse + Pydantic validatsiya. Xato itemlar tashlanadi."""
        if not raw or not raw.strip():
            return []

        # JSON massivni topish (Gemini ba'zan qo'shimcha matn qo'shadi)
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            logger.warning("JSON massiv topilmadi: %s", raw[:100])
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.error("JSON decode xatosi: %s | raw: %s", e, raw[:200])
            return []

        if not isinstance(data, list):
            return []

        result: list[TransactionItem] = []
        for item_data in data:
            try:
                item = TransactionItem.model_validate(item_data)
                result.append(item)
            except Exception as e:
                logger.warning("Invalid transaction item filtered out: %s | error: %s", item_data, e)
                # Noto'g'ri ma'lumot tashlanadi — bazaga SAQLANMAYDI

        return result
