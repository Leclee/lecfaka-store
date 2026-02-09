"""鎻掍欢鍟嗗簵閰嶇疆"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://lecfaka:lecfaka123@localhost:5432/lecfaka_store"
    secret_key: str = "store-secret-key-change-this"
    debug: bool = True


settings = Settings()