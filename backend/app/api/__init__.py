from fastapi import APIRouter, FastAPI

from app.core.config import get_settings

from . import health, testcases


def get_api_router() -> APIRouter:
    """
    Aggregate and return the root API router.
    """
    root_router = APIRouter()

    root_router.include_router(
        health.router,
        prefix="",
        tags=["health"],
    )

    root_router.include_router(
        testcases.router,
        prefix="/testcases",
        tags=["testcases"],
    )

    return root_router


def register_routes(app: FastAPI) -> None:
    """
    Attach all API routes to the FastAPI application.
    """
    settings = get_settings()
    api_router = get_api_router()
    app.include_router(api_router, prefix=settings.api_prefix)
