from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from schemas.testcase import (
    GenerateTestCasesRequest,
    TestCaseGenerationRequest,
    TestCaseListResponse,
    TestCaseResponse,
)
from services.testcase_service import TestCaseService
from utils.excel_exporter import test_cases_to_excel


router = APIRouter()


def get_service() -> TestCaseService:
    return TestCaseService()


@router.post(
    "/from-requirements",
    response_model=TestCaseListResponse,
    summary="Generate test cases from requirements",
)
async def generate_from_requirements(
    payload: TestCaseGenerationRequest,
    service: TestCaseService = Depends(get_service),
) -> TestCaseListResponse:
    """
    Generate a set of candidate test cases from high-level requirements.
    """
    test_cases = await service.generate_test_cases(payload)
    responses: List[TestCaseResponse] = [
        await service.to_response(tc) for tc in test_cases
    ]
    return TestCaseListResponse(items=responses, total=len(responses))


@router.get(
    "/{test_case_id}",
    response_model=TestCaseResponse,
    summary="Get a single test case by id",
)
async def get_test_case(
    test_case_id: UUID,
    service: TestCaseService = Depends(get_service),
) -> TestCaseResponse:
    test_case = await service.get_by_id(test_case_id)
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case {test_case_id} not found",
        )
    return await service.to_response(test_case)


@router.get(
    "",
    response_model=TestCaseListResponse,
    summary="List all generated test cases (in-memory)",
)
async def list_test_cases(
    service: TestCaseService = Depends(get_service),
) -> TestCaseListResponse:
    items = [await service.to_response(tc) for tc in await service.list_all()]
    return TestCaseListResponse(items=items, total=len(items))


@router.post(
    "/generate-test-cases",
    response_model=TestCaseListResponse,
    summary="Generate test cases using the AI model",
)
async def generate_test_cases_with_ai(
    payload: GenerateTestCasesRequest,
    generate_excel: bool = False,
    service: TestCaseService = Depends(get_service),
) -> TestCaseListResponse | FileResponse:
    """
    Generate structured test cases using the configured LLM (Ollama or OpenAI).
    """
    try:
        cases = await service.generate_ai_test_cases(payload)

        if generate_excel:
            excel_path = test_cases_to_excel(cases)
            return FileResponse(
                excel_path,
                media_type=(
                    "application/"
                    "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                filename="generated-test-cases.xlsx",
            )

        responses: List[TestCaseResponse] = [
            await service.to_response(tc) for tc in cases
        ]
        return TestCaseListResponse(items=responses, total=len(responses))
    except ValueError as exc:
        msg = str(exc)
        if "Unsupported LLM provider" in msg or "API key" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned invalid structure: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate test cases from AI: {exc}",
        ) from exc
