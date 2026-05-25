import logging
from datetime import date

from app.models.debt import Debt, DebtDirection
from app.repositories.debt_repo import DebtRepository
from app.schemas.debt import DebtItem

logger = logging.getLogger("services")


class DebtService:
    def __init__(self, debt_repo: DebtRepository) -> None:
        self.repo = debt_repo

    async def save_from_ai(self, user_id: int, item: DebtItem) -> Debt:
        due = date.fromisoformat(item.due_date) if item.due_date else None
        debt = await self.repo.create_for_user(
            user_id=user_id,
            person_name=item.person_name,
            direction=item.direction,
            amount=item.amount,
            currency=item.currency,
            due_date=due,
            note=item.note,
        )
        await self.repo.commit()
        return debt

    async def get_active(self, user_id: int) -> list[Debt]:
        return await self.repo.get_active_for_user(user_id)

    async def mark_paid(self, debt_id: int, user_id: int) -> Debt | None:
        return await self.repo.mark_paid(debt_id, user_id)
