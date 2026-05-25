from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Valid slugs ───────────────────────────────────────────────────────────────
VALID_CATEGORIES = {
    "ovqat", "taxi", "transport", "kiyim", "internet",
    "telefon", "uy", "kommunal", "oqish", "salomatlik",
    "kongilochar", "ish_haqi", "qarz", "sovga", "boshqa",
}

VALID_CURRENCIES = {"UZS", "USD", "RUB"}
VALID_TYPES = {"income", "expense"}
VALID_PAYMENT_METHODS = {"cash", "card", "click", "payme", "bank", "other"}


# ── AI input schema (validated Gemini output) ─────────────────────────────────

class TransactionItem(BaseModel):
    """Gemini AI dan kelgan bitta tranzaksiya — validatsiyadan o'tadi."""

    type: str = Field(..., description="income yoki expense")
    amount: Decimal = Field(..., gt=0, le=999_999_999_999, description="Manfiy bo'lmasin")
    currency: str = Field("UZS")
    category: str = Field("boshqa")
    payment_method: str = Field("cash")
    note: Optional[str] = Field(None, max_length=500)
    date: Optional[str] = Field(None, description="ISO format: 2025-05-26")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_TYPES:
            raise ValueError(f"type must be income or expense, got: {v!r}")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.upper().strip()
        return v if v in VALID_CURRENCIES else "UZS"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        v = v.lower().strip()
        return v if v in VALID_CATEGORIES else "boshqa"

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        v = v.lower().strip()
        return v if v in VALID_PAYMENT_METHODS else "cash"

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if not v:
            return None
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            return None

    @property
    def transaction_date(self) -> date:
        if self.date:
            return date.fromisoformat(self.date)
        return date.today()


# ── DB output schema ──────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    id: int
    type: str
    amount: Decimal
    currency: str
    category_name: Optional[str]
    payment_method: str
    note: Optional[str]
    transaction_date: date

    model_config = {"from_attributes": True}
