from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://erp:erp@localhost:5434/erp"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()