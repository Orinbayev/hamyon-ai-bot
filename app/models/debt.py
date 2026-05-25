from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DebtDirection(str, PyEnum):
    GIVEN = "given"        # Men berdim — men kreditor
    RECEIVED = "received"  # Men oldim — men debitor


class DebtStatus(str, PyEnum):
    ACTIVE = "active"
    PAID = "paid"
    PARTIAL = "partial"


class Debt(Base, TimestampMixin):
    __tablename__ = "debts"
    __table_args__ = (
        Index("ix_debts_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── CRITICAL: every debt record is OWNED by exactly one user ────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    person_name: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[DebtDirection] = mapped_column(Enum(DebtDirection), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="UZS", nullable=False)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[DebtStatus] = mapped_column(
        Enum(DebtStatus), default=DebtStatus.ACTIVE, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="debts", lazy="noload")

    @property
    def remaining_amount(self) -> Decimal:
        return self.amount - self.paid_amount

    def __repr__(self) -> str:
        return f"<Debt user_id={self.user_id} {self.direction} {self.person_name} {self.amount}>"
