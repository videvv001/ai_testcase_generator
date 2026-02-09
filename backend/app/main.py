"""
Single entrypoint for the AI Testcase Generator service.

Run from backend directory: uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.core.logging_config import configure_logging
from app.api import register_routes


def create_app() -> FastAPI:
    """
    Application factory for the FastAPI app.
    """
    configure_logging()

    app = FastAPI(
        title="AI Testcase Generator",
        description=(
            "Internal backend service for generating test cases from "
            "requirements and specifications. Prepared for integration with "
            "local Ollama and OpenAI."
        ),
        version="0.1.0",
    )

    register_routes(app)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
