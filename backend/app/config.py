from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads from environment variables (and a .env file if present).
    # extra="ignore" means future env vars we haven't defined yet won't crash startup.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "BI Copilot"
    # Default matches docker-compose; override via the DATABASE_URL env var.
    database_url: str = "postgresql://app:changeme@db:5432/bicopilot"


settings = Settings()
