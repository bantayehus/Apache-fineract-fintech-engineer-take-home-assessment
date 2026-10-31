from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://integration:integration@localhost:5433/integration"
    fineract_base_url: str = "http://localhost:8080/fineract-provider/api/v1"
    fineract_username: str = "mifos"
    fineract_password: str = "password"
    erp_base_url: str = "http://localhost:8001"
    auth_token: str = "assessment-secret-token"
    log_level: str = "INFO"
    max_retry_attempts: int = 5
    retry_backoff_seconds: float = 2.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()