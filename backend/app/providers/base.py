from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Interface for LLM providers used to generate test cases.

    Implementations (Ollama, OpenAI, etc.) are responsible for
    HTTP calls, retries, and returning raw model output.
    """

    @abstractmethod
    async def generate_test_cases(self, prompt: str, **kwargs: object) -> str:
        """
        Send the prompt to the LLM and return the raw response text.

        Callers are responsible for parsing and validating the output
        (e.g. JSON with test_cases array). Optional kwargs (e.g. coverage_level)
        may be used by providers for token allocation or other behavior.
        """
        ...
