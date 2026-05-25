from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    # PostgreSQL — async URL: postgresql+asyncpg://user:pass@host/db
    database_url: str = Field(..., alias="DATABASE_URL")

    # Gemini AI
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL")

    debug: bool = Field(False, alias="DEBUG")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
