"""Configuration module that loads environment variables from ``.env``."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration validated at import time."""

    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")

    env: Literal["dev", "staging", "prod", "test"] = Field(default="dev", alias="ENV")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_iss: str = Field(default="northstar", alias="JWT_ISS")
    jwt_aud: str | None = Field(default=None, alias="JWT_AUD")
    tenant_id: str = Field(default="tenant1", alias="TENANT_ID")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    postgres_host: str = Field(..., alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    postgres_sslmode: str | None = Field(default="require", alias="POSTGRES_SSLMODE")
    postgres_sslrootcert: str | None = Field(default=None, alias="POSTGRES_SSLROOTCERT")
    postgres_connect_timeout: int | None = Field(default=30, alias="POSTGRES_CONNECT_TIMEOUT")

    qdrant_url: str = Field(..., alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    queue_mode: Literal["direct", "redis"] = Field(default="redis", alias="QUEUE_MODE")

    # --- LLM provider & models -------------------------------------------------
    # Default provider is OpenAI (GPT-5) to "Enable GPT-5 for all clients" by default
    llm_provider: Literal["openai", "cerebras"] = Field(default="openai", alias="LLM_PROVIDER")

    # OpenAI config (used when llm_provider == "openai")
    openai_base_url: str | None = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    # Default to GPT-5 as requested
    openai_model: str | None = Field(default="gpt-5", alias="OPENAI_MODEL")

    # Cerebras config (used when llm_provider == "cerebras")
    cerebras_base_url: str | None = Field(default=None, alias="CEREBRAS_BASE_URL")
    cerebras_api_key: str | None = Field(default=None, alias="CEREBRAS_API_KEY")
    cerebras_model: str | None = Field(default=None, alias="CEREBRAS_MODEL")

    atlassian_base_url: str | None = Field(default=None, alias="ATLASSIAN_BASE_URL")
    atlassian_email: str | None = Field(default=None, alias="ATLASSIAN_EMAIL")
    atlassian_api_token: str | None = Field(default=None, alias="ATLASSIAN_API_TOKEN")
    atlassian_space: str | None = Field(default=None, alias="ATLASSIAN_CONFLUENCE_SPACE")

    github_webhook_secret: str | None = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")
    github_app_token: str | None = Field(default=None, alias="GITHUB_APP_TOKEN")

    hybrid_lambda: float = Field(default=0.6, alias="HYBRID_LAMBDA")
    bge_model: str = Field(default="BAAI/bge-m3", alias="BGE_MODEL")


settings = Settings()
