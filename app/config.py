"""Configuration centralisée de l'application, lue depuis les variables d'environnement."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    postgres_user: str = "sales_agent"
    postgres_password: str = "sales_agent"
    postgres_db: str = "sales_agent"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    app_env: str = "development"
    log_level: str = "INFO"

    # WhatsApp Cloud API (Meta) — voir docs/whatsapp_integration.md
    whatsapp_verify_token: str = "changeme"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v21.0"

    # Twilio WhatsApp (mode "Try out WhatsApp")
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    # Whapi.Cloud (alternative sans Meta ni Twilio)
    whapi_token: str = ""
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()