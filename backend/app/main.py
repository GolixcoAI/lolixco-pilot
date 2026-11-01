from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes.analysis import router as analysis_router
from .routes.health import router as health_router
from .routes.media import router as media_router
from .routes.projects import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Validate application configuration during startup."""
    active_settings = get_settings()
    if active_settings.DATABASE_PROVIDER == "supabase":
        if not active_settings.SUPABASE_URL or not active_settings.SUPABASE_PUBLISHABLE_KEY:
            raise RuntimeError(
                "Invalid startup configuration: SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY "
                "must be configured when DATABASE_PROVIDER is 'supabase'."
            )
    yield


settings = get_settings()

app = FastAPI(
    title="LolixCopilot API",
    description="Backend API and processing pipeline for LolixCopilot video editing assistant",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS configuration strictly restricted to allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router, prefix="/api")
app.include_router(health_router, prefix="")
app.include_router(projects_router)
app.include_router(media_router)
app.include_router(analysis_router)
