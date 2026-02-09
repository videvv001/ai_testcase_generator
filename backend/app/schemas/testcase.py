import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, conint, constr, model_validator

logger = logging.getLogger(__name__)

CoverageLevel = Literal["low", "medium", "high", "comprehensive"]
VALID_COVERAGE_LEVELS: tuple[str, ...] = ("low", "medium", "high", "comprehensive")

ModelProfile = Literal["fast", "smart", "private"]


class TestCaseGenerationRequest(BaseModel):
    project: constr(min_length=1) = Field(
        ...,
        description="Name of the project or product.",
    )
    component: constr(min_length=1) = Field(
        ...,
        description="Sub-system or component under test (e.g. 'auth-service').",
    )
    requirements: List[constr(min_length=1)] = Field(
        ...,
        description="High-level requirements or user stories to generate test cases from.",
        min_items=1,
    )
    max_cases: conint(ge=1, le=200) = Field(
        default=20,
        description="Upper bound on the number of generated test cases.",
    )
    created_by: Optional[constr(min_length=1)] = Field(
        default=None,
        description="Optional identifier for the engineer requesting generation.",
    )


class TestCase(BaseModel):
    """
    Canonical test case schema used throughout the application.

    This model is used both for in-memory storage and as the shape
    of AI-generated test cases.
    """

    id: UUID = Field(default_factory=uuid4)

    # Core test case fields
    test_scenario: constr(min_length=1)
    test_description: constr(min_length=1)
    pre_condition: constr(min_length=1)
    test_data: constr(min_length=1)
    test_steps: List[constr(min_length=1)] = Field(
        ...,
        min_items=1,
        description="Ordered list of steps to perform in the test.",
    )
    expected_result: constr(min_length=1)

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    created_by: Optional[constr(min_length=1)] = None


class TestCaseResponse(BaseModel):
    """
    API response representation of a test case.
    """

    id: UUID
    test_scenario: str
    test_description: str
    pre_condition: str
    test_data: str
    test_steps: List[str]
    expected_result: str
    created_at: datetime
    created_by: Optional[str] = None


class TestCaseListResponse(BaseModel):
    items: List[TestCaseResponse]
    total: int


def _number_of_cases_to_coverage_level(n: int) -> CoverageLevel:
    """Map deprecated number_of_cases to coverage_level."""
    if n <= 5:
        return "low"
    if n <= 15:
        return "medium"
    if n <= 30:
        return "high"
    return "comprehensive"


class GenerateTestCasesRequest(BaseModel):
    """
    Schema for requesting automatic test case generation from the AI.

    Uses risk-based coverage_level; the AI determines how many test cases
    to generate based on the requested depth. Optional number_of_cases
    is deprecated and mapped to coverage_level (1-5→low, 6-15→medium,
    16-30→high, 31+→comprehensive).
    """

    feature_name: constr(min_length=1) = Field(
        ...,
        description="Human-readable name of the feature under test.",
    )
    feature_description: constr(min_length=1) = Field(
        ...,
        description="Detailed description of the feature and its behavior.",
    )
    coverage_level: CoverageLevel = Field(
        default="medium",
        description="Risk-based coverage depth: low, medium, high, or comprehensive.",
    )
    allowed_actions: Optional[str] = Field(
        default=None,
        description="Optional comma/newline-separated allowed actions to include in context.",
    )
    excluded_features: Optional[str] = Field(
        default=None,
        description="Optional comma/newline-separated excluded features to include in context.",
    )
    number_of_cases: Optional[conint(ge=1, le=200)] = Field(
        default=None,
        description="(Deprecated) If provided, mapped to coverage_level; prefer coverage_level.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider: 'ollama', 'openai', or 'gemini'. Derived from model_id when model_id is set.",
    )
    model_profile: Optional[ModelProfile] = Field(
        default=None,
        description="(Legacy) UI profile: 'fast' (gpt-4o-mini), 'smart' (gpt-4o), 'private' (Ollama). Prefer model_id.",
    )
    model_id: Optional[str] = Field(
        default=None,
        description="Model identifier: gpt-4o-mini, gpt-4o, gemini-2.5-flash, llama-3.3-70b-versatile, llama3.2:3b. When set, provider is derived from it.",
    )

    @model_validator(mode="before")
    @classmethod
    def map_number_of_cases_to_coverage(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        n = data.get("number_of_cases")
        if n is not None:
            level = _number_of_cases_to_coverage_level(n)
            data = {**data, "coverage_level": level}
            logger.warning(
                "number_of_cases is deprecated; mapped to coverage_level=%s. "
                "Migrate to coverage_level (low|medium|high|comprehensive).",
                level,
                extra={"number_of_cases": n, "coverage_level": level},
            )
        return data


# --- Batch generation ---

FeatureResultStatus = Literal["pending", "generating", "completed", "failed"]


class FeatureConfig(BaseModel):
    """One feature configuration in a batch request."""

    feature_name: constr(min_length=1) = Field(
        ...,
        description="Human-readable name of the feature under test.",
    )
    feature_description: constr(min_length=1) = Field(
        ...,
        description="Detailed description of the feature and its behavior.",
    )
    allowed_actions: Optional[str] = Field(
        default=None,
        description="Optional allowed actions (comma/newline separated).",
    )
    excluded_features: Optional[str] = Field(
        default=None,
        description="Optional excluded features (comma/newline separated).",
    )
    coverage_level: CoverageLevel = Field(
        default="medium",
        description="Risk-based coverage depth for this feature.",
    )


class BatchGenerateRequest(BaseModel):
    """Request to start a batch of feature generations."""

    provider: Optional[str] = Field(
        default=None,
        description="LLM provider: 'ollama', 'openai', or 'gemini'. Derived from model_id when model_id is set.",
    )
    model_profile: Optional[ModelProfile] = Field(
        default=None,
        description="(Legacy) UI profile. Prefer model_id.",
    )
    model_id: Optional[str] = Field(
        default=None,
        description="Model identifier: gpt-4o-mini, gpt-4o, gemini-2.5-flash, llama-3.3-70b-versatile, llama3.2:3b. When set, provider is derived from it.",
    )
    features: List[FeatureConfig] = Field(
        ...,
        min_length=1,
        description="List of feature configurations to generate test cases for.",
    )


class BatchGenerateResponse(BaseModel):
    """Response after submitting a batch job."""

    batch_id: str = Field(..., description="Unique identifier for the batch.")


class BatchFeatureResult(BaseModel):
    """Status and optional results for one feature in a batch."""

    feature_id: str = Field(..., description="Unique identifier for this feature in the batch.")
    feature_name: str = Field(..., description="Display name of the feature.")
    status: FeatureResultStatus = Field(
        ...,
        description="pending | generating | completed | failed.",
    )
    items: Optional[List[TestCaseResponse]] = Field(
        default=None,
        description="Generated test cases when status is completed.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when status is failed.",
    )


class BatchStatusResponse(BaseModel):
    """Current status and results of a batch job."""

    batch_id: str = Field(..., description="Batch identifier.")
    status: Literal["pending", "running", "completed", "partial"] = Field(
        ...,
        description="pending=not started, running=at least one generating, completed=all done success, partial=at least one failed.",
    )
    features: List[BatchFeatureResult] = Field(
        ...,
        description="Per-feature status and results.",
    )
