import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings with environment validation.

    Secrets must never be logged or returned by public API endpoints.
    """

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = Field(
        default="development",
        description="Environment: development, test, production",
    )
    ALLOWED_ORIGINS: list[str] | str = Field(
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
        default=120,
        gt=0,
        le=300,
        description="Max allowed video length in seconds (default 120 for hackathon demo)",
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

    # External Provider Configs
    MODEL_API_KEY: str = Field(default="", description="Meta Model API Key (server-only)")
    META_BASE_URL: str = Field(
        default="https://api.meta.ai/v1",
        description="Meta Model API base URL",
    )
    META_MODEL: str = Field(
        default="muse-spark-1.3",
        description="Meta Model API model identifier",
    )
    AI_PROVIDER: str = Field(
        default="mock",
        description="Active AI provider: 'baseten', 'meta', or 'mock' (default: mock)",
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
    USE_MODAL_MEDIA_WORKER: bool = Field(
        default=False,
        description="Whether to offload media probing and audio extraction to Modal CPU worker",
    )
    MODAL_MEDIA_WORKER_APP: str = Field(
        default="lolixcopilot-media-worker",
        description="Modal App name for media processing worker",
    )
    USE_AWS_LAMBDA_MEDIA_WORKER: bool = Field(
        default=False,
        description="Whether to offload media probing, proxy, beats, and cuts to AWS Lambda",
    )
    AWS_LAMBDA_MEDIA_FUNCTION: str = Field(
        default="lolixcopilot-media-processor",
        description="AWS Lambda function name for serverless media processing",
    )

    DATABASE_PROVIDER: str = Field(
        default="memory",
        description="Active database provider: 'memory' or 'supabase' (default: memory)",
    )
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_PUBLISHABLE_KEY: str = Field(
        default="",
        description="Supabase publishable key (anon key) for PostgREST client API requests",
    )
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
    ALLOW_DEV_TEST_AUTH: bool = Field(
        default=False,
        description="Explicit development-only toggle to allow raw UUID test authentication",
    )
    AWS_REGION: str = Field(default="ap-south-1", description="AWS S3 Region")
    AWS_S3_BUCKET: str = Field(default="", description="Private AWS S3 Bucket Name")
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS Access Key ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS Secret Access Key")
    AWS_PROFILE: str = Field(default="", description="Optional AWS CLI profile name")
    USE_MOCK_STORAGE: bool = Field(
        default=False, description="Explicitly force in-memory mock storage provider"
    )

    @model_validator(mode="after")
    def validate_database_provider(self) -> "Settings":
        valid_providers = ("memory", "supabase")
        if self.DATABASE_PROVIDER not in valid_providers:
            allowed = ", ".join(repr(p) for p in valid_providers)
            raise ValueError(
                f"Invalid DATABASE_PROVIDER '{self.DATABASE_PROVIDER}'. Must be one of: {allowed}"
            )
        if self.DATABASE_PROVIDER == "supabase":
            if not self.SUPABASE_URL or not self.SUPABASE_PUBLISHABLE_KEY:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured "
                    "when DATABASE_PROVIDER is 'supabase'"
                )
        valid_ai_providers = ("mock", "baseten", "meta")
        if self.AI_PROVIDER.lower() not in valid_ai_providers:
            allowed_ai = ", ".join(repr(p) for p in valid_ai_providers)
            raise ValueError(
                f"Invalid AI_PROVIDER '{self.AI_PROVIDER}'. Must be one of: {allowed_ai}"
            )
        return self

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
