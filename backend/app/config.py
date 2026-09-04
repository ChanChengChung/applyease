from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"

    # Deployment release tag/commit. This value is intentionally safe to
    # expose in the readiness response for rollout verification.
    app_version: str = "development"

    database_url: str = "postgresql+psycopg://applyease:applyease@localhost:5433/applyease"

    upload_dir: str = "./uploads"

    max_upload_bytes: int = 10 * 1024 * 1024

    max_document_pages: int = 50

    max_document_text_characters: int = 200_000

    max_docx_uncompressed_bytes: int = 25 * 1024 * 1024

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM integration is opt-in so document uploads remain usable offline.

    ai_extraction_enabled: bool = False

    ai_job_analysis_enabled: bool = False

    ai_material_generation_enabled: bool = False

    ai_application_form_enabled: bool = False

    # Interview debrief coaching is a separate opt-in AI capability.  The
    # deterministic feedback path remains available when this is disabled or
    # when every configured provider is unavailable.
    ai_interview_review_enabled: bool = False

    screenshot_ocr_enabled: bool = False

    max_screenshot_bytes: int = 5 * 1024 * 1024

    max_job_import_bytes: int = 2 * 1024 * 1024

    max_job_import_characters: int = 50_000

    job_import_timeout_seconds: float = 10.0

    job_import_max_requests: int = 20

    job_import_rate_limit_window_seconds: int = 60 * 60

    llm_provider: str = "ollama"

    llm_fallback_provider: str = "gemini"

    ollama_base_url: str = "http://localhost:11434"

    ollama_model: str = "qwen3:4b"
    rag_embedding_model: str = "nomic-embed-text"
    milvus_uri: str = "http://localhost:19530"
    rag_generation_enabled: bool = True

    gemini_api_key: str = ""

    gemini_model: str = "gemini-2.5-flash"

    # Alibaba Cloud Model Studio / DashScope exposes an OpenAI-compatible
    # endpoint. A workspace-scoped key must be paired with that workspace's
    # exact base URL; never place either value in browser-side VITE_ settings.
    dashscope_api_key: str = ""

    dashscope_base_url: str = ""

    dashscope_model: str = "qwen-plus"

    dashscope_max_requests_per_minute: int = 10

    llm_timeout_seconds: float = 30.0

    llm_max_retries: int = 2

    gemini_max_requests_per_minute: int = 10

    # Opportunity Radar uses Brave's independent web index for the optional
    # guided public-web search.  Keep this server-side only: browser clients
    # must never receive the subscription token.
    brave_search_api_key: str = ""

    brave_search_timeout_seconds: float = 10.0

    brave_search_max_requests: int = 3

    # Opportunity Radar prefers Bocha's domestic Web Search API. Brave remains
    # an optional secondary provider when Bocha is unavailable.
    bocha_search_api_key: str = ""

    bocha_search_timeout_seconds: float = 10.0

    bocha_search_max_requests: int = 3

    # Official ATS board indexes change far less frequently than users rerun a
    # search. A short cache keeps Opportunity Radar responsive without making
    # job listings stale for a whole session.
    official_job_feed_cache_seconds: int = 300

    # Account-level quotas are enforced in PostgreSQL before AI work starts.
    # They protect both local compute and Gemini's free tier across workers.
    ai_generation_max_requests: int = 30

    ai_generation_rate_limit_window_seconds: int = 15 * 60

    cloud_ocr_max_requests: int = 10

    cloud_ocr_rate_limit_window_seconds: int = 60 * 60

    llm_max_prompt_characters: int = 40_000

    auth_secret: str = "change-me-in-production"

    auth_token_ttl_seconds: int = 60 * 60 * 24

    auth_cookie_name: str = "applyease_session"

    auth_csrf_cookie_name: str = "applyease_csrf"

    auth_cookie_secure: bool = False

    auth_max_failed_attempts: int = 5

    auth_max_failed_ip_attempts: int = 25

    auth_rate_limit_window_seconds: int = 15 * 60

    auth_require_verified_email: bool = False

    email_verification_ttl_seconds: int = 60 * 60 * 24

    password_reset_ttl_seconds: int = 60 * 60

    account_email_max_requests: int = 3

    account_email_max_ip_requests: int = 20

    account_email_rate_limit_window_seconds: int = 60 * 60

    account_token_max_failed_attempts: int = 20

    mfa_login_ttl_seconds: int = 5 * 60

    mfa_max_failed_attempts: int = 10

    mfa_recovery_code_count: int = 8

    frontend_base_url: str = "http://127.0.0.1:5173"

    mail_delivery_mode: Literal["file", "smtp", "disabled"] = "file"

    mail_file_dir: str = "./dev-mailbox"

    mail_from: str = "ApplyEase <no-reply@applyease.local>"

    smtp_host: str = ""

    smtp_port: int = 587

    smtp_username: str = ""

    smtp_password: str = ""

    smtp_starttls: bool = True

    # A single-process scheduler is sufficient for the local/demo deployment.
    # Delivery rows have a database uniqueness constraint, so multiple API
    # workers can also run the scan safely without duplicate emails.
    deadline_reminder_scheduler_enabled: bool = True

    deadline_reminder_interval_seconds: int = 900

    enforce_https: bool = False

    allowed_hosts: str = "localhost,127.0.0.1,testserver"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized.startswith(("postgresql+psycopg://", "postgresql://", "sqlite://")):

            raise ValueError("DATABASE_URL must use PostgreSQL/psycopg or SQLite")

        return normalized

    @field_validator("llm_max_retries")
    @classmethod
    def validate_non_negative_numbers(cls, value: int) -> int:

        if value < 0:

            raise ValueError("LLM_MAX_RETRIES cannot be negative")

        return value

    @field_validator(
        "max_upload_bytes",
        "max_document_pages",
        "max_document_text_characters",
        "max_docx_uncompressed_bytes",
        "max_screenshot_bytes",
        "max_job_import_bytes",
        "max_job_import_characters",
        "job_import_max_requests",
        "job_import_rate_limit_window_seconds",
        "gemini_max_requests_per_minute",
        "dashscope_max_requests_per_minute",
        "brave_search_max_requests",
        "bocha_search_max_requests",
        "official_job_feed_cache_seconds",
        "ai_generation_max_requests",
        "ai_generation_rate_limit_window_seconds",
        "cloud_ocr_max_requests",
        "cloud_ocr_rate_limit_window_seconds",
        "llm_max_prompt_characters",
        "auth_token_ttl_seconds",
        "auth_max_failed_attempts",
        "auth_max_failed_ip_attempts",
        "auth_rate_limit_window_seconds",
        "email_verification_ttl_seconds",
        "password_reset_ttl_seconds",
        "account_email_max_requests",
        "account_email_max_ip_requests",
        "account_email_rate_limit_window_seconds",
        "account_token_max_failed_attempts",
        "mfa_login_ttl_seconds",
        "mfa_max_failed_attempts",
        "mfa_recovery_code_count",
        "smtp_port",
        "deadline_reminder_interval_seconds",
    )
    @classmethod
    def validate_positive_numbers(cls, value: int) -> int:

        if value <= 0:

            raise ValueError("size and rate-limit settings must be greater than zero")

        return value

    @field_validator(
        "llm_timeout_seconds",
        "job_import_timeout_seconds",
        "brave_search_timeout_seconds",
        "bocha_search_timeout_seconds",
    )
    @classmethod
    def validate_timeout(cls, value: float) -> float:

        if value <= 0:

            raise ValueError("LLM_TIMEOUT_SECONDS must be greater than zero")

        return value

    @model_validator(mode="after")
    def validate_environment(self):
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

        if any(not origin.startswith(("http://", "https://")) for origin in origins):

            raise ValueError("CORS_ORIGINS entries must be HTTP(S) origins")

        if self.app_env == "production":

            if self.database_url.startswith("sqlite"):

                raise ValueError(
                    "Production requires PostgreSQL; SQLite is only supported locally and in tests"
                )

            if "*" in origins:

                raise ValueError("Production CORS_ORIGINS cannot contain a wildcard")

            if "applyease:applyease@" in self.database_url:

                raise ValueError(
                    "Production DATABASE_URL cannot use the default development credentials"
                )

            if self.auth_secret == "change-me-in-production" or len(self.auth_secret) < 32:

                raise ValueError("Production AUTH_SECRET must be at least 32 characters")

            if not self.auth_cookie_secure:

                raise ValueError("Production AUTH_COOKIE_SECURE must be true")

            if not self.enforce_https:

                raise ValueError("Production ENFORCE_HTTPS must be true")

            if (
                not [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
                or "*" in self.allowed_hosts
            ):

                raise ValueError("Production ALLOWED_HOSTS must contain explicit hostnames")

            if not self.auth_require_verified_email:

                raise ValueError("Production AUTH_REQUIRE_VERIFIED_EMAIL must be true")

            if self.mail_delivery_mode != "smtp" or not self.smtp_host:

                raise ValueError("Production requires SMTP mail delivery and SMTP_HOST")

            if not self.smtp_starttls:

                raise ValueError("Production SMTP_STARTTLS must be true")

            if not self.frontend_base_url.startswith("https://"):

                raise ValueError("Production FRONTEND_BASE_URL must use HTTPS")

            if self.screenshot_ocr_enabled and not self.gemini_api_key:

                raise ValueError("Production SCREENSHOT_OCR_ENABLED requires GEMINI_API_KEY")

            if not self.app_version.strip() or self.app_version.casefold() in {
                "development",
                "unversioned",
                "unknown",
            }:

                raise ValueError("Production APP_VERSION must identify an immutable release")

            if len(self.app_version) > 120:

                raise ValueError("Production APP_VERSION must be at most 120 characters")

        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
