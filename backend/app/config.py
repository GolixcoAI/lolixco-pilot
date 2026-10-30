import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment validation.

    Secrets must never be logged or returned by public API endpoints.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = Field(
        default="development",
        description="Environment: development, test, production",
    )
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins for web client",
    )

    # Server limits
    MAX_UPLOAD_BYTES: int = Field(
        default=104857600,
        gt=0,
        le=524288000,
        description="Max video upload size in bytes (default 100 MB, limit 500 MB)",
    )
    MAX_VIDEO_SECONDS: int = Field(
        default=60,
        gt=0,
        le=300,
        description="Max allowed video length in seconds (default 60)",
    )
    SIGNED_URL_TTL_SECONDS: int = Field(
        default=900,
        gt=60,
        le=3600,
        description="Short-lived signed URL validity in seconds (default 15m)",
    )
    VIDEO_RETENTION_DAYS: int = Field(
        default=7,
        gt=0,
        le=90,
        description="Data retention period in days",
    )
    DAILY_ANALYSIS_LIMIT: int = Field(
        default=5,
        gt=0,
        description="Max analyses allowed per user per day in demo mode",
    )

    # External Provider Configs (optional for Phase 0 scaffold & testing)
    MODEL_API_KEY: str = Field(default="", description="Meta Model API Key (server-only)")
    AI_PROVIDER: str = Field(
        default="mock",
        description="Active AI provider: 'baseten' or 'mock' (default: mock for credit safety)",
    )
    BASETEN_API_KEY: str = Field(
        default="", description="Baseten API Key for model inference (server-only, never logged)"
    )
    BASETEN_BASE_URL: str = Field(
        default="https://inference.baseten.co/v1",
        description="Baseten OpenAI-compatible inference base URL",
    )
    BASETEN_MODEL: str = Field(
        default="meta-models/muse-spark-open-1026",
        description="Baseten model identifier for Muse Spark Open",
    )
    AI_REQUEST_TIMEOUT_SECONDS: int = Field(
        default=120,
        gt=5,
        le=300,
        description="Timeout in seconds for model inference requests",
    )
    AI_MAX_RETRIES: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max retries on transient errors (429, 502, 503, 504)",
    )
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", description="Supabase service role secret")
    SUPABASE_JWT_SECRET: str = Field(
        default="", description="Supabase JWT secret for symmetric HS256 auth verification"
    )
    SUPABASE_JWKS_URL: str = Field(
        default="",
        description="Optional Supabase JWKS URL (defaults to {SUPABASE_URL}/auth/v1/jwks)",
    )
    SUPABASE_JWT_AUDIENCE: str = Field(
        default="authenticated",
        description="Expected JWT audience claim (default: authenticated)",
    )
    SUPABASE_JWT_ISSUER: str = Field(
        default="",
        description="Expected JWT issuer claim (e.g. {SUPABASE_URL}/auth/v1)",
    )
    AWS_REGION: str = Field(default="ap-south-1", description="AWS S3 Region")
    AWS_S3_BUCKET: str = Field(default="", description="Private AWS S3 Bucket Name")
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS Access Key ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS Secret Access Key")
    AWS_PROFILE: str = Field(default="", description="Optional AWS CLI profile name")
    USE_MOCK_STORAGE: bool = Field(
        default=False, description="Explicitly force in-memory mock storage provider"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return ["http://localhost:3000"]
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
