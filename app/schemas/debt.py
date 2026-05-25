from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

VALID_DIRECTIONS = {"given", "received"}


class DebtItem(BaseModel):
    """Gemini AI dan kelgan qarz ma'lumoti."""

    direction: str = Field("given", description="given (berdim) yoki received (oldim)")
    person_name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, le=999_999_999_999)
    currency: str = Field("UZS")
    due_date: Optional[str] = None
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        v = v.lower().strip()
        return v if v in VALID_DIRECTIONS else "given"

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: str | None) -> str | None:
        if not v:
            return None
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            return None


class DebtOut(BaseModel):
    id: int
    person_name: str
    direction: str
    amount: Decimal
    paid_amount: Decimal
    currency: str
    status: str
    due_date: Optional[date]
    note: Optional[str]

    model_config = {"from_attributes": True}
