"""Deprecated: use providers.factory.get_provider() and LLMProvider instead."""

from __future__ import annotations

from typing import Any, Dict, List

from app.providers.ollama_provider import OllamaProvider


class LlmClient:
    def __init__(self, client: Any = None) -> None:
        self._provider = OllamaProvider(client=client)

    async def close(self) -> None:
        await self._provider.close()

    async def generate_testcases(
        self, prompt: str, context: Dict[str, Any], max_items: int
    ) -> List[Dict[str, Any]]:
        return []

    async def generate_test_cases(self, prompt: str) -> str:
        return await self._provider.generate_test_cases(prompt)
