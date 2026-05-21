from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/acid_talent'
    jwt_secret: str = 'change-me'
    access_token_expire_minutes: int = 480

    s3_endpoint_url: str | None = None
    s3_region: str = 'us-east-1'
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = 'acid-talent'
    s3_public_url_base: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = 'no-reply@acidtalent.local'

    ai_api_key: str | None = None
    ai_api_base_url: str = 'https://api.openai.com/v1'
    ai_model: str = 'gpt-4o-mini'
    ai_timeout_seconds: int = 45

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()