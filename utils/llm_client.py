"""
Deprecated: use providers.factory.get_provider() and LLMProvider instead.

This module is kept for backward compatibility. It delegates to OllamaProvider.
"""

from __future__ import annotations

from typing import Any, Dict, List

from providers.ollama_provider import OllamaProvider


class LlmClient:
    """
    Deprecated wrapper around Ollama. Use get_provider("ollama") instead.
    """

    def __init__(self, client: Any = None) -> None:
        self._provider = OllamaProvider(client=client)

    async def close(self) -> None:
        await self._provider.close()

    async def generate_testcases(
        self,
        prompt: str,
        context: Dict[str, Any],
        max_items: int,
    ) -> List[Dict[str, Any]]:
        """Deprecated. Use generate_test_cases(prompt) and parse JSON."""
        return []

    async def generate_test_cases(self, prompt: str) -> str:
        """Delegates to OllamaProvider."""
        return await self._provider.generate_test_cases(prompt)
