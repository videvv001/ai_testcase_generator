from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Sequence
from uuid import UUID

from providers.base import LLMProvider
from providers.factory import get_provider
from schemas.testcase import (
    GenerateTestCasesRequest,
    TestCase,
    TestCaseGenerationRequest,
    TestCaseResponse,
)
from utils.prompt_builder import build_testcase_prompt


logger = logging.getLogger(__name__)

# Layer order: each level builds on the previous. Higher coverage includes all lower layers.
COVERAGE_LAYERS: tuple[str, ...] = ("core", "validation", "edge", "destructive")

LAYER_FOCUS: Dict[str, str] = {
    "core": (
        "Generate the minimum set of test cases required for basic functionality, "
        "happy paths, and primary CRUD flows only."
    ),
    "validation": (
        "Generate test cases focused on field validation, required inputs, "
        "format errors, and user mistakes. Do not duplicate core flows."
    ),
    "edge": (
        "Generate test cases for boundary values, unusual inputs, "
        "state transitions, and concurrency risks. Do not duplicate core or validation cases."
    ),
    "destructive": (
        "Generate test cases for production-level risks: data corruption scenarios, "
        "conflicting operations, and resilience failures. Do not duplicate existing cases."
    ),
}

# Which layers run per coverage_level (cumulative).
COVERAGE_LEVEL_LAYERS: Dict[str, tuple[str, ...]] = {
    "low": ("core",),
    "medium": ("core", "validation"),
    "high": ("core", "validation", "edge"),
    "comprehensive": ("core", "validation", "edge", "destructive"),
}


class TestCaseService:
    """
    Application service responsible for generating and managing test cases.

    Business logic is concentrated here to keep route handlers thin.
    LLM calls go through the provider abstraction (Ollama or OpenAI).
    """

    def __init__(self) -> None:
        self._store: Dict[UUID, TestCase] = {}

    @staticmethod
    def _extract_json_object(raw_output: str) -> str:
        """
        Best-effort extraction of the JSON object from an LLM response.

        Some models may wrap the JSON with markdown fences or short prose
        despite strict instructions. To make the system more robust, we:
        - Strip leading/trailing whitespace.
        - Take the substring from the first '{' to the last '}' if both exist.
        """
        text = raw_output.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return text
        return text[start : end + 1]

    @staticmethod
    def _existing_cases_to_json(cases: Sequence[TestCase]) -> str:
        """Serialize existing test cases to a minimal JSON string for the prompt (duplicate prevention)."""
        if not cases:
            return ""
        minimal = [
            {
                "test_scenario": tc.test_scenario,
                "test_description": tc.test_description,
                "test_steps": tc.test_steps,
            }
            for tc in cases
        ]
        return json.dumps(minimal, indent=2)

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for similarity comparison."""
        s = re.sub(r"\s+", " ", title.lower().strip())
        return s

    @staticmethod
    def _remove_near_duplicate_titles(cases: List[TestCase]) -> List[TestCase]:
        """
        Remove redundant cases when titles are near-duplicates (exact or one contains the other).
        Preserve the most detailed version (longer steps + expected_result).
        """
        if len(cases) <= 1:
            return cases
        result: List[TestCase] = []
        for tc in cases:
            key = TestCaseService._normalize_title(tc.test_scenario)
            detail = len(" ".join(tc.test_steps)) + len(tc.expected_result)
            found = False
            for i, existing in enumerate(result):
                existing_key = TestCaseService._normalize_title(existing.test_scenario)
                if key == existing_key or key in existing_key or existing_key in key:
                    existing_detail = len(" ".join(existing.test_steps)) + len(existing.expected_result)
                    if detail > existing_detail:
                        result[i] = tc
                    found = True
                    break
            if not found:
                result.append(tc)
        return result

    async def _generate_layer(
        self,
        provider: LLMProvider,
        user_instructions: str,
        layer: str,
        existing_cases: List[TestCase],
    ) -> List[TestCase]:
        """
        Generate one layer of test cases. Sequentially called by the pipeline.
        When existing_cases is non-empty, the prompt instructs the model not to duplicate.
        """
        focus = LAYER_FOCUS.get(layer, LAYER_FOCUS["core"])
        existing_json = self._existing_cases_to_json(existing_cases) if existing_cases else ""

        prompt = build_testcase_prompt(
            user_instructions=user_instructions,
            coverage_focus=focus,
            existing_test_cases_json=existing_json if existing_json else None,
        )

        raw_output = await provider.generate_test_cases(prompt)

        try:
            cleaned = self._extract_json_object(raw_output)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse LLM JSON output for layer %s",
                layer,
                extra={"error": str(exc), "raw_preview": raw_output[:500]},
            )
            raise

        if not isinstance(parsed, dict):
            raise ValueError("LLM output must be a JSON object with a 'test_cases' field")
        raw_cases = parsed.get("test_cases")
        if not isinstance(raw_cases, list):
            raise ValueError("LLM output 'test_cases' field must be a JSON array")

        validated: List[TestCase] = [
            TestCase.model_validate(self._clean_test_case_data(item))
            for item in raw_cases
        ]
        return validated

    @staticmethod
    def _clean_test_case_data(test_case_data: dict) -> dict:
        """
        Ensure required fields are present and not empty.

        Some LLMs omit or return empty values for certain fields despite
        instructions. This method provides sensible defaults to prevent
        Pydantic validation errors.
        """
        if not (test_case_data.get("test_scenario") or "").strip():
            test_case_data["test_scenario"] = "Test scenario as described"
        if not (test_case_data.get("test_description") or "").strip():
            test_case_data["test_description"] = "Verify behavior per requirements"
        if not (test_case_data.get("pre_condition") or "").strip():
            test_case_data["pre_condition"] = "No specific preconditions required"
        if not (test_case_data.get("test_data") or "").strip():
            test_case_data["test_data"] = "Standard test data as per feature requirements"
        if not (test_case_data.get("expected_result") or "").strip():
            test_case_data["expected_result"] = (
                "Behavior matches the test scenario and acceptance criteria."
            )
        if not test_case_data.get("test_steps") or len(test_case_data.get("test_steps", [])) == 0:
            test_case_data["test_steps"] = ["1. Execute the test scenario as described"]
        return test_case_data

    async def generate_test_cases(
        self, payload: TestCaseGenerationRequest
    ) -> List[TestCase]:
        logger.info(
            "Generating test cases",
            extra={
                "project": payload.project,
                "component": payload.component,
                "requirements_count": len(payload.requirements),
                "max_cases": payload.max_cases,
            },
        )

        generated: List[TestCase] = []

        for idx, requirement in enumerate(payload.requirements, start=1):
            if len(generated) >= payload.max_cases:
                break

            scenario = f"[{payload.component}] Requirement {idx}"
            description = requirement.strip()

            test_steps = [
                f"Review requirement: {requirement}",
                "Identify primary user flow and edge cases.",
                "Execute user flow in a controlled environment.",
                "Record observed behavior and compare with acceptance criteria.",
            ]

            expected_result = (
                "System behavior matches the requirement and acceptance criteria "
                "without regressions in related components."
            )

            test_case = TestCase(
                test_scenario=scenario,
                test_description=description,
                pre_condition="System is in a stable state and all prerequisites are met.",
                test_data="As required to exercise the described requirement.",
                test_steps=test_steps,
                expected_result=expected_result,
                created_by=payload.created_by,
            )

            self._store[test_case.id] = test_case
            generated.append(test_case)

        return generated

    async def generate_ai_test_cases(
        self,
        payload: GenerateTestCasesRequest,
    ) -> List[TestCase]:
        """
        Layered coverage pipeline: run one or more generation layers in order,
        merge results, then remove near-duplicate titles. Higher coverage_level
        always includes all lower-level test cases.
        """
        provider = get_provider(payload.provider)
        layers = COVERAGE_LEVEL_LAYERS.get(
            payload.coverage_level,
            COVERAGE_LEVEL_LAYERS["medium"],
        )

        logger.info(
            "AI test case generation requested (layered pipeline)",
            extra={
                "feature_name": payload.feature_name,
                "coverage_level": payload.coverage_level,
                "layers": list(layers),
                "provider": getattr(provider, "__class__", {}).__name__,
            },
        )

        user_instructions = (
            f"Feature name: {payload.feature_name}\n"
            f"Feature description: {payload.feature_description}\n"
        )

        accumulated: List[TestCase] = []

        for layer in layers:
            batch = await self._generate_layer(
                provider=provider,
                user_instructions=user_instructions,
                layer=layer,
                existing_cases=accumulated,
            )
            accumulated.extend(batch)
            logger.debug(
                "Layer %s produced %d cases; total so far: %d",
                layer,
                len(batch),
                len(accumulated),
            )

        accumulated = self._remove_near_duplicate_titles(accumulated)
        return accumulated

    async def get_by_id(self, test_case_id: UUID) -> TestCase | None:
        return self._store.get(test_case_id)

    async def list_all(self) -> List[TestCase]:
        return list(self._store.values())

    async def to_response(self, test_case: TestCase) -> TestCaseResponse:
        return TestCaseResponse(
            id=test_case.id,
            test_scenario=test_case.test_scenario,
            test_description=test_case.test_description,
            pre_condition=test_case.pre_condition,
            test_data=test_case.test_data,
            test_steps=test_case.test_steps,
            expected_result=test_case.expected_result,
            created_at=test_case.created_at,
            created_by=test_case.created_by,
        )
