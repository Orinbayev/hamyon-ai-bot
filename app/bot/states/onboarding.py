from aiogram.fsm.state import State, StatesGroup


class OnboardingState(StatesGroup):
    waiting_for_name = State()
