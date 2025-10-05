"""Configuration module that loads environment variables from ``.env``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_ENV_PATH = Path(".env")
if _BASE_ENV_PATH.exists():
    load_dotenv(_BASE_ENV_PATH, override=False)

_LOCAL_ENV_PATH = Path(".env.local")
if "PYTEST_CURRENT_TEST" not in os.environ and _LOCAL_ENV_PATH.exists():
    load_dotenv(_LOCAL_ENV_PATH, override=False)


class Settings(BaseSettings):
    """Application configuration validated at import time."""

    model_config = SettingsConfigDict(env_file=(".env",), extra="ignore")

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
    qdrant_run_index_migration: bool = Field(default=False, alias="QDRANT_RUN_INDEX_MIGRATION")
    qdrant_autofix_index_missing: bool = Field(default=False, alias="QDRANT_AUTOFIX_INDEX_MISSING")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    queue_mode: Literal["direct", "redis"] = Field(default="redis", alias="QUEUE_MODE")
    router_mode: Literal["static", "learned"] = Field(default="static", alias="ROUTER_MODE")
    policy_enforcement: Literal["strict", "permissive"] = Field(
        default="strict", alias="POLICY_ENFORCEMENT"
    )
    policy_deny_projects: list[str] | str | None = Field(
        default=None, alias="POLICY_DENY_PROJECTS"
    )
    policy_proof_mode: bool = Field(default=False, alias="POLICY_PROOF_MODE")
    isolation_report_dir: str = Field(default="./artifacts/isolation", alias="ISOLATION_REPORT_DIR")
    eval_data_dir: str = Field(default="./eval/data", alias="EVAL_DATA_DIR")
    eval_mode: bool = Field(default=False, alias="EVAL_MODE")
    abmap_enabled: bool = Field(default=False, alias="ABMAP_ENABLED")
    confluence_draft_mode: bool = Field(default=False, alias="DRAFT_MODE")

    # --- LLM provider & models -------------------------------------------------
    # Default provider is OpenAI (GPT-5) to "Enable GPT-5 for all clients" by default
    llm_provider: Literal["openai", "cerebras"] = Field(default="cerebras", alias="LLM_PROVIDER")

    # OpenAI config (used when llm_provider == "openai")
    openai_base_url: str | None = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    # Default to GPT-5 as requested
    openai_model: str | None = Field(default="gpt-5", alias="OPENAI_MODEL")

    # Cerebras config (used when llm_provider == "cerebras")
    cerebras_base_url: str | None = Field(default=None, alias="CEREBRAS_BASE_URL")
    cerebras_api_key: str | None = Field(default=None, alias="CEREBRAS_API_KEY")
    cerebras_model: str | None = Field(default=None, alias="CEREBRAS_MODEL")

    atlassian_base_url: str | None = Field(
        default=None,
        alias="ATLASSIAN_BASE_URL",
        validation_alias=AliasChoices("ATLASSIAN_BASE_URL", "ATL_SITE"),
    )
    atlassian_email: str | None = Field(
        default=None,
        alias="ATLASSIAN_EMAIL",
        validation_alias=AliasChoices("ATLASSIAN_EMAIL", "ATL_EMAIL"),
    )
    atlassian_api_token: str | None = Field(
        default=None,
        alias="ATLASSIAN_API_TOKEN",
        validation_alias=AliasChoices("ATLASSIAN_API_TOKEN", "ATL_TOKEN"),
    )
    atlassian_space: str | None = Field(
        default=None,
        alias="ATLASSIAN_CONFLUENCE_SPACE",
        validation_alias=AliasChoices("ATLASSIAN_CONFLUENCE_SPACE", "ATL_SPACE_KEY"),
    )
    atlassian_project_key: str | None = Field(
        default=None,
        alias="ATLASSIAN_PROJECT_KEY",
        validation_alias=AliasChoices("ATLASSIAN_PROJECT_KEY", "ATL_PROJECT_KEY"),
    )
    atlassian_project_id: str | None = Field(
        default=None,
        alias="ATLASSIAN_PROJECT_ID",
        validation_alias=AliasChoices("ATLASSIAN_PROJECT_ID", "ATL_PROJECT_ID"),
    )
    atlassian_space_id: str | None = Field(
        default=None,
        alias="ATLASSIAN_SPACE_ID",
        validation_alias=AliasChoices("ATLASSIAN_SPACE_ID", "ATL_SPACE_ID"),
    )
    atlassian_epic_name_field_id: str | None = Field(
        default=None,
        alias="ATLASSIAN_EPIC_NAME_FIELD_ID",
        validation_alias=AliasChoices("ATLASSIAN_EPIC_NAME_FIELD_ID", "ATL_EPIC_NAME_FIELD_ID"),
    )

    github_webhook_secret: str | None = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")
    github_app_token: str | None = Field(default=None, alias="GITHUB_APP_TOKEN")

    auto_provision_dev_from_gh: bool = Field(
        default=False, alias="AUTO_PROVISION_DEV_FROM_GH"
    )
    enable_review_signals: bool = Field(default=True, alias="ENABLE_REVIEW_SIGNALS")
    skill_baseline_increment: float = Field(default=1.0, alias="SKILL_BASELINE_INCREMENT")
    skill_confidence_default: float = Field(
        default=0.7, alias="SKILL_CONFIDENCE_DEFAULT"
    )
    review_major_rework_penalty: float = Field(
        default=0.5, alias="REVIEW_MAJOR_REWORK_PENALTY"
    )
    review_nit_penalty: float = Field(default=0.1, alias="REVIEW_NIT_PENALTY")
    review_approval_bonus: float = Field(default=0.3, alias="REVIEW_APPROVAL_BONUS")
    review_first_review_multiplier: float = Field(
        default=1.0, alias="REVIEW_FIRST_REVIEW_MULTIPLIER"
    )
    review_cycle_penalty: float = Field(default=0.3, alias="REVIEW_CYCLE_PENALTY")
    review_peer_credit: float = Field(default=0.2, alias="REVIEW_PEER_CREDIT")
    review_peer_credit_cap_per_window: int = Field(
        default=5, alias="REVIEW_PEER_CREDIT_CAP_PER_WINDOW"
    )
    review_peer_credit_window_days: int = Field(
        default=7, alias="REVIEW_PEER_CREDIT_WINDOW_DAYS"
    )
    time_to_merge_threshold_hours: int = Field(
        default=24, alias="TIME_TO_MERGE_THRESHOLD_HOURS"
    )
    time_to_merge_penalty: float = Field(
        default=0.2, alias="TIME_TO_MERGE_PENALTY"
    )
    time_to_merge_bonus: float = Field(default=0.1, alias="TIME_TO_MERGE_BONUS")

    hybrid_lambda: float = Field(default=0.6, alias="HYBRID_LAMBDA")
    bge_model: str = Field(default="BAAI/bge-m3", alias="BGE_MODEL")
    embed_dim: int = Field(default=1024, alias="EMBED_DIM", gt=0)
    trace_mode: bool = Field(default=False, alias="TRACE_MODE")
    trace_sampling: float = Field(default=1.0, alias="TRACE_SAMPLING")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


    @field_validator("database_url", mode="before")
    @classmethod
    def _blank_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("policy_deny_projects", mode="after")
    @classmethod
    def _split_policy_denies(cls, value: str | list[str] | None) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)

settings = Settings()

if os.environ.get("PYTEST_CURRENT_TEST"):
    settings.llm_provider = "cerebras"
    settings.cerebras_api_key = ""
    settings.cerebras_base_url = ""
    settings.cerebras_model = None
