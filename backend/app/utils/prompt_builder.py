from __future__ import annotations

import json
from typing import List, Optional


def build_scenario_extraction_prompt(
    user_instructions: str,
    *,
    layer: str,
    layer_focus: str,
    existing_scenarios_json: Optional[str] = None,
    min_scenarios_hint: Optional[int] = None,
    expansion_request: Optional[str] = None,
) -> str:
    existing_block = ""
    if existing_scenarios_json and existing_scenarios_json.strip():
        existing_block = f"\nYou already listed these scenarios. Do NOT repeat them. Add ONLY new, distinct scenarios:\n{existing_scenarios_json}\n"
    min_hint = ""
    if min_scenarios_hint is not None and min_scenarios_hint > 0:
        min_hint = f"\nAim for at least {min_scenarios_hint} distinct scenarios for this dimension. Be exhaustive.\n"
    expansion_block = ""
    if expansion_request:
        expansion_block = f"\n{expansion_request}\n"
    prompt = f"""
You are a senior QA test architect. Your task is to list ALL distinct test scenarios for one coverage dimension.

Coverage dimension: {layer}
Focus: {layer_focus}
{min_hint}
Rules:
- Do NOT merge scenarios. Each independent validation or flow must be its own scenario.
- Be exhaustive. List every distinct scenario you can identify for this dimension.
- Each scenario should be one short phrase (e.g. "User login with valid credentials", "Reject empty required field").
- Do not write test cases yet; only scenario titles or one-line descriptions.
- Core scenarios (happy path, required validations) are highest priority and must never be skipped.
{existing_block}
{expansion_block}

Input context:
{user_instructions}

Return ONLY valid JSON with this exact structure (no other text, no markdown):
{{"scenarios": ["scenario 1", "scenario 2", ...]}}

Output:
""".strip()
    return prompt


def build_test_expansion_prompt(
    user_instructions: str,
    *,
    layer: str,
    layer_focus: str,
    scenarios: List[str],
    existing_test_cases_json: Optional[str] = None,
) -> str:
    scenarios_json = json.dumps(scenarios, indent=2)
    existing_block = ""
    if existing_test_cases_json and existing_test_cases_json.strip():
        existing_block = f"\nThe following test cases already exist. Do NOT duplicate them:\n{existing_test_cases_json}\n"
    prompt = f"""
You are a senior QA test architect. Convert each listed scenario into one or more structured test cases.

CRITICAL RULES — OUTPUT FORMAT:
- Output ONLY valid JSON. Nothing else.
- Do NOT wrap the JSON in markdown code blocks (no ```json or ```).
- Do NOT add any explanatory text, comments, or prose before or after the JSON.
- Do NOT use single quotes; use double quotes only.
- Do NOT use trailing commas in arrays or objects.
- The response must be parseable by Python json.loads() with no preprocessing.

Coverage dimension: {layer}
Focus: {layer_focus}

Scenarios to expand (each must become at least one test case):
{scenarios_json}
{existing_block}

Rules:
- Minimum one test case per scenario. Create additional test cases when variations (e.g. different inputs, boundaries) are needed.
- Never summarize multiple distinct failures or validations into one test case.
- Quality is more important than brevity. Each test case must be concrete and executable.
- test_steps must be ordered and numbered (e.g. "1. Do X", "2. Do Y").
- pre_condition, test_data, expected_result must be non-empty strings.

Use this exact JSON structure (top-level key must be "test_cases"):
{{
  "test_cases": [
    {{
      "test_scenario": "short title",
      "test_description": "what is validated",
      "pre_condition": "conditions before test",
      "test_data": "input/state required",
      "test_steps": ["1. step", "2. step"],
      "expected_result": "expected outcome"
    }}
  ]
}}

Input context:
{user_instructions}

Output ONLY the JSON object, no other text:
""".strip()
    return prompt


def build_testcase_prompt(
    user_instructions: str,
    *,
    coverage_focus: str,
    existing_test_cases_json: Optional[str] = None,
    project: Optional[str] = None,
    component: Optional[str] = None,
    target_count: Optional[int] = None,
) -> str:
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
    target_count_line = ""
    if target_count is not None and target_count > 0:
        target_count_line = f"\nGenerate approximately {target_count} distinct test cases for this batch.\n"
    prompt = f"""
You are a senior QA test architect designing a new test suite from scratch.
Focus on identifying the most important risks first.

Your task is to generate high-quality, structured software test cases based on the provided feature description and requirements.
{existing_block}

Coverage focus for this batch: {coverage_focus}
{target_count_line}

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
