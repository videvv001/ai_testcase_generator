"""
Reusable token allocation helpers for LLM providers.

Estimates prompt token usage and computes safe max_tokens for completion
based on model context window, coverage level, and safety buffer.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Coverage level → max output tokens cap (configurable limits).
COVERAGE_MAX_TOKENS: dict[str, int] = {
    "low": 1000,
    "medium": 2500,
    "high": 5000,
    "comprehensive": 7000,
}

# Default max_tokens when coverage level is unknown.
DEFAULT_COVERAGE_MAX_TOKENS: int = 2500

# Safety buffer reserved (not used for output).
SAFETY_BUFFER_TOKENS: int = 1000

# Maximum fraction of context window allowed for prompt + output (0.7 = 70%).
MAX_CONTEXT_FRACTION: float = 0.70


def _get_context_window(model_name: str) -> int:
    """Return context window size for known OpenAI models. Default 128k."""
    windows: dict[str, int] = {
        "gpt-4o-mini": 128_000,
        "gpt-4o": 128_000,
        "gpt-4o-nano": 128_000,
        "gpt-4-turbo": 128_000,
        "gpt-4": 8_192,
        "gpt-4-32k": 32_768,
        "gpt-3.5-turbo": 16_385,
    }
    for key, size in windows.items():
        if key in model_name.lower():
            return size
    return 128_000


def _estimate_prompt_tokens(prompt: str, model_name: str) -> int:
    """Estimate number of tokens in prompt using tiktoken for the given model."""
    try:
        import tiktoken
    except ImportError:
        return max(1, len(prompt) // 4)

    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(prompt))


def calculate_dynamic_max_tokens(
    prompt: str,
    coverage_level: str,
    model_name: str = "gpt-4o-mini",
    context_window: Optional[int] = None,
    safety_buffer: int = SAFETY_BUFFER_TOKENS,
    max_context_fraction: float = MAX_CONTEXT_FRACTION,
) -> int:
    """
    Compute a safe max_tokens value for completion.

    - Estimates prompt token count with tiktoken.
    - Uses model context window (or lookup by model_name).
    - Reserves a safety buffer (default 1000 tokens).
    - Caps output by coverage level: low=1000, medium=2500, high=5000, comprehensive=7000.
    - Never exceeds max_context_fraction (default 70%) of the context window.
    """
    prompt_tokens = _estimate_prompt_tokens(prompt, model_name)
    model_limit = context_window if context_window is not None else _get_context_window(model_name)
    effective_cap = int(model_limit * max_context_fraction)
    available = effective_cap - prompt_tokens - safety_buffer
    available = max(0, available)

    coverage_cap = COVERAGE_MAX_TOKENS.get(
        coverage_level.strip().lower(),
        DEFAULT_COVERAGE_MAX_TOKENS,
    )
    max_tokens = min(available, coverage_cap)

    logger.info(
        "Token allocation: prompt_tokens=%s max_tokens=%s model_limit=%s",
        prompt_tokens,
        max_tokens,
        model_limit,
        extra={
            "prompt_tokens": prompt_tokens,
            "max_tokens": max_tokens,
            "model_limit": model_limit,
        },
    )
    return max_tokens
