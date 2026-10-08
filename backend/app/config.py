from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

class Settings(BaseSettings):
    mysql_database: str = "marketing"
    mysql_user: str = "marketing"
    mysql_password: str = "marketing_local_change_me"
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_days: int = 7
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:latest"
    ollama_timeout_seconds: int = 240
    ai_daily_limit: int = 30


    @property
    def google_ready(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and len(self.session_secret) >= 32)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )

    @property
    def database_url(self) -> URL:
        return URL.create("mysql+pymysql", username=self.mysql_user,
                          password=self.mysql_password, host=self.db_host,
                          port=self.db_port, database=self.mysql_database,
                          query={"charset": "utf8mb4"})

settings = Settings()
