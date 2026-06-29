from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads from environment variables (and a .env file if present).
    # extra="ignore" means future env vars we haven't defined yet won't crash startup.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "BI Copilot"
    # Default matches docker-compose; override via the DATABASE_URL env var.
    database_url: str = "postgresql://app:changeme@db:5432/bicopilot"

    # --- auth (Milestone 2) ---
    # DEV DEFAULT ONLY. For anything real, set JWT_SECRET in a .env file.
    jwt_secret: str = "dev-only-change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- uploads (Milestone 3) ---
    max_upload_mb: int = 25          # reject files bigger than this
    max_rows: int = 200_000          # reject datasets with more rows than this


settings = Settings()
