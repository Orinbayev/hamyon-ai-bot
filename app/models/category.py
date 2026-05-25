from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.transaction import TransactionType


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        # A slug can be default (user_id=NULL) OR per-user — both allowed
        UniqueConstraint("slug", "user_id", name="uq_category_slug_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # NULL = global default category; non-NULL = user's custom category
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    icon: Mapped[str] = mapped_column(String(10), default="📌")
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User | None"] = relationship(back_populates="categories", lazy="noload")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="category", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Category slug={self.slug!r} default={self.is_default}>"
