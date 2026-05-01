from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set

class Settings(BaseSettings):
    # Application Context
    APP_NAME: str = "Project Khione Backend"
    ENVIRONMENT: str = "development"
    
    # Kiwoom API
    KIWOOM_APP_KEY: str = ""
    KIWOOM_APP_SECRET: str = ""
    KIWOOM_ACCOUNT_NUM: str = ""
    
    # Telegram Security (White-list)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""  # Comma separated string
    
    # OpenDART
    OPENDART_API_KEY: str = ""
    
    # ECOS & Public Data
    ECOS_API_KEY: str = ""
    DATA_GO_KR_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./khione_dev.db"  # Default to local SQLite for dev
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_chat_ids(self) -> Set[int]:
        if not self.TELEGRAM_ALLOWED_CHAT_IDS:
            return set()
        return {int(chat_id.strip()) for chat_id in self.TELEGRAM_ALLOWED_CHAT_IDS.split(",") if chat_id.strip()}

settings = Settings()
