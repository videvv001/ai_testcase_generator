"""
Allow running as: python -m ai_testcase_generator

Delegates to the single entrypoint main.py.
"""
import uvicorn

from .main import create_app


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
