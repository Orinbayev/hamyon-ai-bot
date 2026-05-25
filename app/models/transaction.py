from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TransactionType(str, PyEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Currency(str, PyEnum):
    UZS = "UZS"
    USD = "USD"
    RUB = "RUB"


class PaymentMethod(str, PyEnum):
    CASH = "cash"
    CARD = "card"
    CLICK = "click"
    PAYME = "payme"
    BANK = "bank"
    OTHER = "other"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        # Composite indexes for fast user-filtered queries
        Index("ix_tx_user_date", "user_id", "transaction_date"),
        Index("ix_tx_user_type", "user_id", "type"),
        Index("ix_tx_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── CRITICAL: every transaction is OWNED by exactly one user ────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency), default=Currency.UZS, nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.CASH, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="transactions", lazy="noload")
    category: Mapped["Category | None"] = relationship(
        back_populates="transactions", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Transaction user_id={self.user_id} {self.type} {self.amount}>"
