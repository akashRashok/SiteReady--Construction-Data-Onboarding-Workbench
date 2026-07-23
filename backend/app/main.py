"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.deps import get_repository, get_service


def create_app() -> FastAPI:
    settings = get_settings()
    # Initialise repository / schema at startup
    get_repository()
    get_service()

    app = FastAPI(
        title="Construction Data Onboarding Workbench",
        description="Independent demo. Synthetic data.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
