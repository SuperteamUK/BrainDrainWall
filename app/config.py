from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    apollo_api_key: str = ""
    apollo_base_url: str = "https://api.apollo.io/api/v1"
    request_timeout_seconds: float = 30.0


settings = Settings()
