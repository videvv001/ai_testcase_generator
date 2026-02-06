from __future__ import annotations

from typing import Optional


def build_testcase_prompt(
    user_instructions: str,
    *,
    coverage_focus: str,
    existing_test_cases_json: Optional[str] = None,
    project: Optional[str] = None,
    component: Optional[str] = None,
) -> str:
    """
    Build a strict instruction prompt for the LLM.

    Does not decide coverage strategy; only formats the given
    coverage_focus and optional existing-test-cases block into the prompt.
    """

    context_lines = []
    if project:
        context_lines.append(f"Project: {project}")
    if component:
        context_lines.append(f"Component: {component}")

    context_block = ""
    if context_lines:
        context_block = "\n".join(context_lines) + "\n\n"

    existing_block = ""
    if existing_test_cases_json and existing_test_cases_json.strip():
        existing_block = f"""
The following test cases already exist. Do NOT duplicate them. Generate ONLY new scenarios that expand coverage.
Do NOT regenerate, rewrite, improve, or replace existing test cases.
Only produce brand new scenarios.

Existing test cases:
{existing_test_cases_json}

Expand the existing test suite to increase coverage. Do not replace existing tests. Only add new ones.
"""

    prompt = f"""
You are a senior QA test architect designing a new test suite from scratch.
Focus on identifying the most important risks first.

Your task is to generate high-quality, structured software test cases based on the provided feature description and requirements.
{existing_block}

Coverage focus for this batch: {coverage_focus}

Follow these rules strictly:
- Return ONLY valid JSON.
- Ensure the response is parseable by Python's json.loads().
- Do not include any explanations, comments, or prose.
- Do not use markdown or code fences.
- Do not add extra top-level fields beyond what is in the example.
- Do not include trailing commas anywhere in the JSON.
- Ensure all strings use double quotes.
- Every test case must be realistic, concise, and directly related to the described feature.
- The test_steps list must be ordered and each step must begin with a step number prefix (e.g. "1. Do X", "2. Do Y", "3. Do Z").
- Avoid repeating identical step sequences across different test cases when possible; each test case should focus on its unique validation objective.
- Do not repeat setup or environmental conditions from pre_condition inside test_steps; steps must focus on the core actions and validations of the scenario.
- Use concrete test data values instead of generic placeholders.

Use the following JSON structure exactly, with a single top-level object containing a test_cases array:

{{
  "test_cases": [
    {{
      "test_scenario": "short, descriptive test scenario title",
      "test_description": "concise description of what is being validated",
      "pre_condition": "conditions that must hold before executing the test",
      "test_data": "description of the input data or state required for the test",
      "test_steps": [
        "1. first action in the test",
        "2. second action in the test",
        "3. third action in the test"
      ],
      "expected_result": "clear expected outcome after executing all steps"
    }}
  ]
}}

Input context:
{context_block}{user_instructions}

Now output only the JSON object with the test_cases array, with no additional text.
""".strip()

    return prompt
