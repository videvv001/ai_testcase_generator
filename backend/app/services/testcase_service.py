from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Sequence
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.providers.factory import get_provider, model_id_to_provider
from app.schemas.testcase import (
    BatchFeatureResult,
    BatchStatusResponse,
    FeatureConfig,
    FeatureResultStatus,
    GenerateTestCasesRequest,
    TestCase,
    TestCaseGenerationRequest,
    TestCaseResponse,
)
from app.utils.embeddings import (
    deduplicate_indices_by_embeddings,
    deduplicate_scenarios,
)
from app.utils.prompt_builder import (
    build_scenario_extraction_prompt,
    build_test_expansion_prompt,
)


logger = logging.getLogger(__name__)


@dataclass
class _FeatureResultState:
    feature_id: str
    feature_name: str
    status: FeatureResultStatus
    items: List[TestCase] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class _BatchState:
    batch_id: str
    status: Literal["pending", "running", "completed", "partial"]
    features: Dict[str, _FeatureResultState] = field(default_factory=dict)
    provider: Optional[str] = None
    model_profile: Optional[str] = None
    model_id: Optional[str] = None
    config_by_feature_id: Dict[str, FeatureConfig] = field(default_factory=dict)


# Coverage dimensions (scenario-driven). Higher coverage includes all lower dimensions.
LAYER_FOCUS: Dict[str, str] = {
    "core": (
        "Fundamental workflows, happy paths, and required validations. "
        "Highest priority: never skip basic flows or mandatory checks."
    ),
    "validation": (
        "Field validation, required inputs, format errors, and user input mistakes. "
        "Do not duplicate core flows."
    ),
    "negative": (
        "Invalid inputs, error paths, rejection cases, and user mistakes. "
        "Each independent failure mode is its own scenario."
    ),
    "boundary": (
        "Boundary values, unusual inputs, limits, and edge values. "
        "Do not duplicate core, validation, or negative scenarios."
    ),
    "state": (
        "State transitions, multi-step flows, and state-dependent behavior. "
        "Do not duplicate earlier dimensions."
    ),
    "security": (
        "Security-related scenarios: auth, authorization, injection, sensitive data. "
        "Do not duplicate earlier dimensions."
    ),
    "destructive": (
        "Data corruption, conflicting operations, resilience failures, and recovery. "
        "Do not duplicate earlier dimensions."
    ),
}

# Which dimensions run per coverage_level (cumulative). Order matters.
COVERAGE_LEVEL_LAYERS: Dict[str, tuple[str, ...]] = {
    "low": ("core",),
    "medium": ("core", "validation", "negative"),
    "high": ("core", "validation", "negative", "boundary", "state"),
    "comprehensive": (
        "core",
        "validation",
        "negative",
        "boundary",
        "state",
        "security",
        "destructive",
    ),
}

# Safety floor: if the LLM returns fewer scenarios than this for a layer, re-prompt for expansion.
# No cap on maximum.
MIN_SCENARIOS_PER_LAYER: Dict[str, int] = {
    "core": 5,
    "validation": 6,
    "negative": 6,
    "boundary": 8,
    "state": 6,
    "security": 6,
    "destructive": 6,
}

# Embedding deduplication threshold (cosine similarity). Above this, treat as duplicate.
EMBEDDING_DEDUP_THRESHOLD: float = 0.90

# Scenario-level semantic dedup: same threshold; applied after each layer's scenario extraction.
SCENARIO_DEDUP_THRESHOLD: float = 0.90


class TestCaseService:
    """
    Application service responsible for generating and managing test cases.

    Business logic is concentrated here to keep route handlers thin.
    LLM calls go through the provider abstraction (Ollama or OpenAI).
    """

    def __init__(self) -> None:
        self._store: Dict[UUID, TestCase] = {}
        self._batch_store: Dict[str, _BatchState] = {}

    @staticmethod
    def _strip_markdown_code_blocks(text: str) -> str:
        """Remove markdown code blocks (```json ... ``` or ``` ... ```)."""
        stripped = text.strip()
        # Remove opening ```json or ```
        for pattern in (r"^```\s*json\s*\n?", r"^```\s*\n?"):
            stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
        # Remove closing ```
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        return stripped.strip()

    @staticmethod
    def _extract_json_object(raw_output: str) -> str:
        text = raw_output.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return text
        return text[start : end + 1]

    @staticmethod
    def _repair_json(text: str) -> str:
        """
        Fix common LLM JSON output errors before parsing.
        - Removes trailing commas before } or ].
        - Inserts missing comma between adjacent } and { (e.g. in test_cases array).
        """
        # Remove trailing commas before } or ] (with optional whitespace/newlines)
        repaired = re.sub(r",(\s*[}\]])", r"\1", text)
        # Insert missing comma between adjacent } and { (common in arrays of objects)
        repaired = re.sub(r"}\s*{", "}, {", repaired)
        return repaired

    @staticmethod
    def _parse_json_lenient(text: str) -> dict:
        """
        Parse JSON; on failure apply repair and retry; then try json_repair if available.
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        repaired = TestCaseService._repair_json(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            try:
                import json_repair  # type: ignore[import-untyped]
                return json_repair.loads(repaired)
            except ImportError:
                raise e
            except Exception:
                raise e

    @staticmethod
    def _parse_llm_response(response_text: str, expected_key: str) -> dict:
        """
        Parse LLM response into a JSON object with robust handling of markdown and format.
        - Strips markdown code blocks (```json ... ```).
        - Handles extra whitespace and newlines.
        - Logs raw response preview for debugging.
        - Raises clear errors with content snippet when parsing or validation fails.
        """
        if not response_text or not response_text.strip():
            logger.warning("LLM returned empty response")
            raise ValueError("LLM returned empty response; expected JSON object.")
        raw_preview = response_text[:500] if len(response_text) > 500 else response_text
        logger.debug("LLM raw response (first 500 chars): %s", raw_preview)
        cleaned = TestCaseService._strip_markdown_code_blocks(response_text)
        cleaned = TestCaseService._extract_json_object(cleaned)
        try:
            parsed = TestCaseService._parse_json_lenient(cleaned)
        except json.JSONDecodeError as exc:
            snippet = (cleaned[:300] + "...") if len(cleaned) > 300 else cleaned
            logger.error(
                "JSON parse error: %s; snippet: %s",
                exc,
                snippet,
                extra={"raw_preview": raw_preview},
            )
            raise ValueError(
                f"LLM output is not valid JSON: {exc}. "
                f"Content received (first 300 chars): {snippet!r}"
            ) from exc
        if not isinstance(parsed, dict):
            logger.error(
                "Parsed result is not a dict: type=%s, value=%s",
                type(parsed).__name__,
                str(parsed)[:200],
            )
            raise ValueError(
                f"LLM output must be a JSON object with a '{expected_key}' field; "
                f"received type {type(parsed).__name__}."
            )
        # Normalize key: accept test_cases or testCases, scenarios for scenarios
        key = expected_key
        if key not in parsed and key == "test_cases" and "testCases" in parsed:
            parsed["test_cases"] = parsed.pop("testCases")
        if key not in parsed:
            keys_preview = list(parsed.keys())[:10]
            logger.error(
                "Parsed object missing expected key '%s'; keys: %s",
                expected_key,
                keys_preview,
                extra={"parsed_keys": list(parsed.keys())},
            )
            raise ValueError(
                f"LLM output must be a JSON object with a '{expected_key}' field. "
                f"Received keys: {keys_preview!r}."
            )
        logger.debug("Parsed JSON has key '%s' with %s items", key, len(parsed[key]) if isinstance(parsed.get(key), list) else "?")
        return parsed

    @staticmethod
    def _existing_cases_to_json(cases: Sequence[TestCase]) -> str:
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
        s = re.sub(r"\s+", " ", title.lower().strip())
        return s

    @staticmethod
    def _remove_near_duplicate_titles(cases: List[TestCase]) -> List[TestCase]:
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

    async def _extract_scenarios(
        self,
        provider: LLMProvider,
        user_instructions: str,
        layer: str,
        coverage_level: str,
        model_profile: Optional[str],
        existing_scenarios: Optional[List[str]] = None,
        expansion_request: Optional[str] = None,
    ) -> List[str]:
        focus = LAYER_FOCUS.get(layer, LAYER_FOCUS["core"])
        min_hint = MIN_SCENARIOS_PER_LAYER.get(layer)
        existing_json = json.dumps(existing_scenarios, indent=2) if existing_scenarios else None

        prompt = build_scenario_extraction_prompt(
            user_instructions=user_instructions,
            layer=layer,
            layer_focus=focus,
            existing_scenarios_json=existing_json,
            min_scenarios_hint=min_hint,
            expansion_request=expansion_request,
        )
        model_id = getattr(self, "_current_model_id", None)
        raw_output = await provider.generate_test_cases(
            prompt,
            coverage_level=coverage_level,
            model_profile=model_profile,
            model_id=model_id,
        )
        logger.debug(
            "Scenario extraction raw response length=%s (first 500): %s",
            len(raw_output) if raw_output else 0,
            (raw_output[:500] if raw_output else ""),
        )
        parsed = self._parse_llm_response(raw_output, "scenarios")
        raw_scenarios = parsed.get("scenarios")
        if not isinstance(raw_scenarios, list):
            raise ValueError(
                "LLM output 'scenarios' field must be a JSON array; "
                f"got {type(raw_scenarios).__name__}."
            )
        scenarios = [str(s).strip() for s in raw_scenarios if s]
        if not scenarios:
            raise ValueError("LLM returned no scenarios")

        min_required = MIN_SCENARIOS_PER_LAYER.get(layer)
        if min_required is not None and len(scenarios) < min_required and not expansion_request:
            expansion_request = (
                f"You returned {len(scenarios)} scenarios. We need at least {min_required} distinct scenarios "
                f"for this dimension. List more distinct scenarios; do not merge or summarize."
            )
            logger.info(
                "Re-prompting for more scenarios: layer=%s current=%s min=%s",
                layer,
                len(scenarios),
                min_required,
            )
            return await self._extract_scenarios(
                provider=provider,
                user_instructions=user_instructions,
                layer=layer,
                coverage_level=coverage_level,
                model_profile=model_profile,
                existing_scenarios=scenarios,
                expansion_request=expansion_request,
            )
        return scenarios

    async def _expand_scenarios_to_tests(
        self,
        provider: LLMProvider,
        user_instructions: str,
        layer: str,
        scenarios: List[str],
        existing_cases: List[TestCase],
        coverage_level: str,
        model_profile: Optional[str],
    ) -> List[TestCase]:
        if not scenarios:
            return []
        focus = LAYER_FOCUS.get(layer, LAYER_FOCUS["core"])
        existing_json = self._existing_cases_to_json(existing_cases) if existing_cases else None

        prompt = build_test_expansion_prompt(
            user_instructions=user_instructions,
            layer=layer,
            layer_focus=focus,
            scenarios=scenarios,
            existing_test_cases_json=existing_json,
        )
        model_id = getattr(self, "_current_model_id", None)
        max_attempts = 3
        base_delay_seconds = 1.0
        last_error: Optional[Exception] = None
        raw_output = ""

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(
                    "Test expansion layer=%s attempt=%s/%s",
                    layer,
                    attempt,
                    max_attempts,
                )
                raw_output = await provider.generate_test_cases(
                    prompt,
                    coverage_level=coverage_level,
                    model_profile=model_profile,
                    model_id=model_id,
                )
                logger.debug(
                    "Test expansion raw response length=%s (first 500): %s",
                    len(raw_output) if raw_output else 0,
                    (raw_output[:500] if raw_output else ""),
                )
                parsed = self._parse_llm_response(raw_output, "test_cases")
                raw_cases = parsed.get("test_cases")
                if not isinstance(raw_cases, list):
                    raise ValueError(
                        "LLM output 'test_cases' field must be a JSON array; "
                        f"got {type(raw_cases).__name__}."
                    )
                validated: List[TestCase] = [
                    TestCase.model_validate(self._clean_test_case_data(item))
                    for item in raw_cases
                ]
                logger.debug(
                    "Test expansion layer=%s parsed %s test cases",
                    layer,
                    len(validated),
                )
                return validated
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "Test expansion layer=%s attempt=%s/%s failed: %s",
                    layer,
                    attempt,
                    max_attempts,
                    exc,
                    extra={"raw_preview": raw_output[:500] if raw_output else ""},
                )
                if attempt < max_attempts:
                    delay = base_delay_seconds * (1.5 ** (attempt - 1))
                    logger.info(
                        "Retrying test expansion in %.1fs (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        max_attempts,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Test expansion failed after %s attempts: %s",
                        max_attempts,
                        exc,
                    )
                    raise
        assert last_error is not None
        raise last_error

    async def _generate_layer(
        self,
        provider: LLMProvider,
        user_instructions: str,
        layer: str,
        existing_cases: List[TestCase],
        coverage_level: str = "medium",
        model_profile: Optional[str] = None,
        model_id: Optional[str] = None,
        scenario_embedding_cache: Optional[Dict[str, List[float]]] = None,
        openai_api_key: Optional[str] = None,
    ) -> List[TestCase]:
        scenarios = await self._extract_scenarios(
            provider=provider,
            user_instructions=user_instructions,
            layer=layer,
            coverage_level=coverage_level,
            model_profile=model_profile,
        )
        logger.debug("Layer %s: extracted %d scenarios", layer, len(scenarios))
        scenarios = await deduplicate_scenarios(
            scenarios,
            api_key=openai_api_key,
            threshold=SCENARIO_DEDUP_THRESHOLD,
            cache=scenario_embedding_cache or {},
        )
        logger.debug("Layer %s: %d scenarios after dedup", layer, len(scenarios))
        cases = await self._expand_scenarios_to_tests(
            provider=provider,
            user_instructions=user_instructions,
            layer=layer,
            scenarios=scenarios,
            existing_cases=existing_cases,
            coverage_level=coverage_level,
            model_profile=model_profile,
        )
        return cases

    @staticmethod
    def _sanitize_unicode(s: str) -> str:
        if not isinstance(s, str):
            return str(s)
        return re.sub(r"[\ud800-\udfff]", "", s)

    @staticmethod
    def _clean_test_case_data(test_case_data: dict) -> dict:
        def _san(s: str) -> str:
            return TestCaseService._sanitize_unicode(s) if isinstance(s, str) else str(s)

        for key in ("test_scenario", "test_description", "pre_condition", "test_data", "expected_result"):
            if test_case_data.get(key) is not None:
                test_case_data[key] = _san(str(test_case_data[key]))
        steps = test_case_data.get("test_steps")
        if isinstance(steps, list):
            test_case_data["test_steps"] = [_san(str(s)) for s in steps]

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

    @staticmethod
    def _case_to_embedding_text(tc: TestCase) -> str:
        steps = " ".join(getattr(tc, "test_steps", []) or [])
        return f"{tc.test_scenario} {tc.test_description} {steps}".strip()

    async def _deduplicate_by_embeddings(
        self,
        cases: List[TestCase],
        *,
        api_key: Optional[str] = None,
        threshold: float = EMBEDDING_DEDUP_THRESHOLD,
    ) -> List[TestCase]:
        if len(cases) <= 1:
            return cases
        texts = [self._case_to_embedding_text(tc) for tc in cases]
        keep_indices = await deduplicate_indices_by_embeddings(
            texts,
            threshold=threshold,
            api_key=api_key,
        )
        if len(keep_indices) == len(cases):
            return cases
        result = [cases[i] for i in keep_indices]
        logger.info(
            "Embedding dedup: %d -> %d cases removed",
            len(cases),
            len(cases) - len(result),
        )
        return result

    async def generate_ai_test_cases(
        self,
        payload: GenerateTestCasesRequest,
    ) -> List[TestCase]:
        payload_model_id = getattr(payload, "model_id", None)
        provider_name = (
            model_id_to_provider(payload_model_id)
            if payload_model_id
            else payload.provider
        )
        provider = get_provider(provider_name)
        self._current_model_id = payload_model_id
        layers = COVERAGE_LEVEL_LAYERS.get(
            payload.coverage_level,
            COVERAGE_LEVEL_LAYERS["medium"],
        )

        logger.info(
            "AI test case generation requested (scenario-driven)",
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
        if getattr(payload, "allowed_actions", None) and str(payload.allowed_actions).strip():
            user_instructions += "\n\nAllowed actions: " + str(payload.allowed_actions).strip()
        if getattr(payload, "excluded_features", None) and str(payload.excluded_features).strip():
            user_instructions += "\n\nExcluded features: " + str(payload.excluded_features).strip()

        settings = get_settings()
        scenario_embedding_cache: Dict[str, List[float]] = {}
        accumulated: List[TestCase] = []
        for layer in layers:
            batch = await self._generate_layer(
                provider=provider,
                user_instructions=user_instructions,
                layer=layer,
                existing_cases=accumulated,
                coverage_level=payload.coverage_level,
                model_profile=getattr(payload, "model_profile", None),
                model_id=getattr(payload, "model_id", None),
                scenario_embedding_cache=scenario_embedding_cache,
                openai_api_key=settings.openai_api_key,
            )
            accumulated.extend(batch)
            logger.debug(
                "Layer %s produced %d cases; total so far: %d",
                layer,
                len(batch),
                len(accumulated),
            )

        accumulated = await self._deduplicate_by_embeddings(
            accumulated,
            api_key=settings.openai_api_key,
            threshold=EMBEDDING_DEDUP_THRESHOLD,
        )
        accumulated = self._remove_near_duplicate_titles(accumulated)
        return accumulated

    async def get_by_id(self, test_case_id: UUID) -> TestCase | None:
        return self._store.get(test_case_id)

    async def delete_test_case(self, test_case_id: UUID) -> bool:
        if test_case_id not in self._store:
            return False
        del self._store[test_case_id]
        for batch in self._batch_store.values():
            for fr in batch.features.values():
                if fr.items:
                    fr.items = [tc for tc in fr.items if tc.id != test_case_id]
        return True

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

    def _feature_config_to_request(
        self,
        config: FeatureConfig,
        provider: Optional[str],
        model_profile: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> GenerateTestCasesRequest:
        return GenerateTestCasesRequest(
            feature_name=config.feature_name,
            feature_description=config.feature_description,
            allowed_actions=config.allowed_actions,
            excluded_features=config.excluded_features,
            coverage_level=config.coverage_level,
            provider=provider,
            model_profile=model_profile,
            model_id=model_id,
        )

    async def _run_one_feature(
        self,
        batch_id: str,
        feature_id: str,
        config: FeatureConfig,
        provider: Optional[str],
    ) -> None:
        batch = self._batch_store.get(batch_id)
        if not batch or feature_id not in batch.features:
            return
        fr = batch.features[feature_id]
        fr.status = "generating"
        try:
            model_profile = getattr(batch, "model_profile", None) if batch else None
            model_id = getattr(batch, "model_id", None) if batch else None
            req = self._feature_config_to_request(config, provider, model_profile, model_id)
            cases = await self.generate_ai_test_cases(req)
            for tc in cases:
                self._store[tc.id] = tc
            fr.items = cases
            fr.status = "completed"
            fr.error = None
        except Exception as exc:
            logger.exception("Batch feature %s failed: %s", feature_id, exc)
            fr.status = "failed"
            fr.error = str(exc)
            fr.items = []
        self._update_batch_status(batch_id)

    def _update_batch_status(self, batch_id: str) -> None:
        batch = self._batch_store.get(batch_id)
        if not batch:
            return
        statuses = [f.status for f in batch.features.values()]
        if all(s == "completed" for s in statuses):
            batch.status = "completed"
        elif any(s == "failed" for s in statuses):
            batch.status = "partial"
        elif any(s in ("generating", "pending") for s in statuses):
            batch.status = "running"
        else:
            batch.status = "completed"

    async def start_batch(
        self,
        provider: Optional[str],
        features: List[FeatureConfig],
        model_profile: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> str:
        if model_id and not provider:
            provider = model_id_to_provider(model_id)
        batch_id = str(uuid4())
        feature_states: Dict[str, _FeatureResultState] = {}
        config_by_feature_id: Dict[str, FeatureConfig] = {}
        for config in features:
            fid = str(uuid4())
            feature_states[fid] = _FeatureResultState(
                feature_id=fid,
                feature_name=config.feature_name,
                status="pending",
            )
            config_by_feature_id[fid] = config
        batch = _BatchState(
            batch_id=batch_id,
            status="running",
            features=feature_states,
            provider=provider,
            model_profile=model_profile,
            model_id=model_id,
            config_by_feature_id=config_by_feature_id,
        )
        self._batch_store[batch_id] = batch

        async def run_all() -> None:
            tasks = [
                self._run_one_feature(batch_id, fid, config, provider)
                for fid, config in batch.config_by_feature_id.items()
            ]
            await asyncio.gather(*tasks)
            self._update_batch_status(batch_id)

        asyncio.create_task(run_all())
        return batch_id

    async def get_batch_status(self, batch_id: str) -> Optional[BatchStatusResponse]:
        batch = self._batch_store.get(batch_id)
        if not batch:
            return None
        feature_results: List[BatchFeatureResult] = []
        for fr in batch.features.values():
            items_resp = None
            if fr.items:
                items_resp = [await self.to_response(tc) for tc in fr.items]
            feature_results.append(
                BatchFeatureResult(
                    feature_id=fr.feature_id,
                    feature_name=fr.feature_name,
                    status=fr.status,
                    items=items_resp,
                    error=fr.error,
                )
            )
        return BatchStatusResponse(
            batch_id=batch.batch_id,
            status=batch.status,
            features=feature_results,
        )

    async def retry_batch_feature(
        self,
        batch_id: str,
        feature_id: str,
        provider: Optional[str],
    ) -> bool:
        batch = self._batch_store.get(batch_id)
        if not batch or feature_id not in batch.features:
            return False
        config = batch.config_by_feature_id.get(feature_id)
        if not config:
            return False
        fr = batch.features[feature_id]
        fr.status = "pending"
        fr.error = None
        fr.items = []
        prov = provider if provider is not None else batch.provider
        await self._run_one_feature(batch_id, feature_id, config, prov)
        return True

    async def get_batch_merged_cases(
        self, batch_id: str, dedupe: bool = True
    ) -> List[TestCase]:
        batch = self._batch_store.get(batch_id)
        if not batch:
            return []
        all_cases: List[TestCase] = []
        for fr in batch.features.values():
            if fr.items:
                all_cases.extend(fr.items)
        if dedupe and all_cases:
            all_cases = self._remove_near_duplicate_titles(all_cases)
        return all_cases
