from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import TransactionType
from app.repositories.base import BaseRepository

CATEGORY_DEFAULTS = {
    "ovqat":      ("Ovqat",       "🍽", TransactionType.EXPENSE),
    "taxi":       ("Taxi",        "🚕", TransactionType.EXPENSE),
    "transport":  ("Transport",   "🚌", TransactionType.EXPENSE),
    "kiyim":      ("Kiyim",       "👗", TransactionType.EXPENSE),
    "internet":   ("Internet",    "🌐", TransactionType.EXPENSE),
    "telefon":    ("Telefon",     "📱", TransactionType.EXPENSE),
    "uy":         ("Uy",          "🏠", TransactionType.EXPENSE),
    "kommunal":   ("Kommunal",    "💡", TransactionType.EXPENSE),
    "oqish":      ("O'qish",      "📚", TransactionType.EXPENSE),
    "salomatlik": ("Salomatlik",  "💊", TransactionType.EXPENSE),
    "kongilochar":("Ko'ngilochar","🎭", TransactionType.EXPENSE),
    "ish_haqi":   ("Ish haqi",    "💼", TransactionType.INCOME),
    "qarz":       ("Qarz",        "🤝", TransactionType.EXPENSE),
    "sovga":      ("Sovg'a",      "🎁", TransactionType.EXPENSE),
    "boshqa":     ("Boshqa",      "📌", TransactionType.EXPENSE),
}


class CategoryRepository(BaseRepository[Category]):
    model = Category

    async def get_default(self, slug: str) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                and_(Category.slug == slug, Category.is_default == True)  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, slug: str, user_id: int) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                and_(Category.slug == slug, Category.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_for_user(
        self,
        user_id: int,
        slug: str,
        tx_type: TransactionType,
    ) -> Category:
        # 1. Try global default first
        cat = await self.get_default(slug)
        if cat:
            return cat

        # 2. Try user's own category
        cat = await self.get_for_user(slug, user_id)
        if cat:
            return cat

        # 3. Create user-specific category
        meta = CATEGORY_DEFAULTS.get(slug, ("Boshqa", "📌", tx_type))
        return await self.create(
            user_id=user_id,
            slug=slug,
            name=meta[0],
            icon=meta[1],
            type=tx_type,
            is_default=False,
        )
