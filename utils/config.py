from functools import lru_cache
from urllib.parse import quote, unquote

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def encode_db_url_password(url: str) -> str:
    """
    URL-encode the password inside a postgresql:// URL so passwords containing @ # : / ? % work
    whether or not the user already encoded them. The host part never contains '@', so the LAST '@'
    separates the credentials from the host.
    """
    scheme, sep, rest = url.partition("://")
    if not sep or "@" not in rest:
        return url
    userinfo, host = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return url
    user, password = userinfo.split(":", 1)
    return f"{scheme}://{user}:{quote(unquote(password), safe='')}@{host}"


class Settings(BaseSettings):
    """
    Central application settings, loaded from environment variables / .env file.
    Every value can be overridden per environment (local, docker, cloud) without code changes.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---------- LLM ----------
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model_low: str = Field(default="gpt-5.6-luna", alias="LLM_MODEL_LOW")
    llm_model_medium: str = Field(default="gpt-5.6-terra", alias="LLM_MODEL_MEDIUM")
    llm_model_high: str = Field(default="gpt-5.6-sol", alias="LLM_MODEL_HIGH")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    enable_llm_judge: bool = Field(default=True, alias="ENABLE_LLM_JUDGE")

    # ---------- Database ----------
    # The agent must connect with the READ-ONLY role (analyst_ro), never the owner role.
    database_url: str = Field(
        default="postgresql://analyst_ro:analyst_ro_password@localhost:5432/airbnb",
        alias="DATABASE_URL",
    )
    db_schema: str = Field(default="public", alias="DB_SCHEMA")
    db_statement_timeout_ms: int = Field(default=15000, alias="DB_STATEMENT_TIMEOUT_MS")
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=10, alias="DB_POOL_MAX_SIZE")
    schema_cache_ttl_seconds: int = Field(default=600, alias="SCHEMA_CACHE_TTL_SECONDS")

    # ---------- Agent behaviour ----------
    default_row_limit: int = Field(default=10, alias="DEFAULT_ROW_LIMIT")
    max_row_limit: int = Field(default=500, alias="MAX_ROW_LIMIT")
    max_sql_retries: int = Field(default=2, alias="MAX_SQL_RETRIES")
    max_question_chars: int = Field(default=1000, alias="MAX_QUESTION_CHARS")
    max_history_messages: int = Field(default=6, alias="MAX_HISTORY_MESSAGES")
    rows_for_summary: int = Field(default=30, alias="ROWS_FOR_SUMMARY")
    # Columns that must never be queried or returned (comma separated, case-insensitive).
    sensitive_columns: str = Field(
        default="host_email,host_phone,email,phone,phone_number,password,password_hash,"
        "api_key,secret,token,credit_card,card_number,ssn",
        alias="SENSITIVE_COLUMNS",
    )

    # ---------- API ----------
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")
    app_api_key: str = Field(default="", alias="APP_API_KEY")  # empty = auth disabled (local dev)
    rate_limit_per_minute: int = Field(default=20, alias="RATE_LIMIT_PER_MINUTE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("database_url")
    @classmethod
    def _encode_password(cls, value: str) -> str:
        return encode_db_url_password(value)

    @property
    def sensitive_column_set(self) -> set[str]:
        return {c.strip().lower() for c in self.sensitive_columns.split(",") if c.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
