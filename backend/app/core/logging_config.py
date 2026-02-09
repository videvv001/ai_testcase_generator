import logging
import sys
from typing import Optional

from app.core.config import get_settings


_configured = False


def configure_logging(level_override: Optional[str] = None) -> None:
    """
    Configure structured logging for the service.

    This is idempotent and safe to call multiple times.
    """
    global _configured

    if _configured:
        return

    settings = get_settings()
    log_level = (level_override or settings.log_level).upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    # Reduce noise from underlying libraries in production-like environments.
    for noisy_logger in ("uvicorn", "uvicorn.access", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    _configured = True
