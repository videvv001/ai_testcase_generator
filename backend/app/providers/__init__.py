"""
LLM provider abstraction layer.

All LLM-specific logic lives in provider implementations.
Business logic depends only on the LLMProvider interface.
"""

from app.providers.base import LLMProvider
from app.providers.factory import get_provider

__all__ = ["LLMProvider", "get_provider"]
