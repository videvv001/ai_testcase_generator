/**
 * API request/response types aligned with backend schemas.
 * No prompt, provider, or token details exposed to the UI.
 */

export type CoverageLevel = "low" | "medium" | "high" | "comprehensive";

/** Model identifier sent to backend; provider is derived from it. */
export type ModelId =
  | "gpt-4o-mini"
  | "gpt-4o"
  | "gemini-2.5-flash"
  | "llama-3.3-70b-versatile"
  | "llama3.2:3b";

/** Backend request: when model_id is set, provider is derived from it. */
export type ApiProvider = "ollama" | "openai" | "gemini" | "groq";

export interface GenerateTestCasesRequest {
  feature_name: string;
  feature_description: string;
  coverage_level: CoverageLevel;
  provider?: ApiProvider;
  model_profile?: "fast" | "smart" | "private";
  /** When set, backend derives provider (gpt-4o-mini, gpt-4o -> openai; gemini-2.5-flash -> gemini; llama-3.3-70b-versatile -> groq; llama3.2:3b -> ollama). */
  model_id?: ModelId;
}

export interface TestCaseItem {
  id: string;
  test_scenario: string;
  test_description: string;
  pre_condition: string;
  test_data: string;
  test_steps: string[];
  expected_result: string;
  created_at: string;
  created_by: string | null;
}

export interface TestCaseListResponse {
  items: TestCaseItem[];
  total: number;
}

// --- Batch ---

export type FeatureResultStatus = "pending" | "generating" | "completed" | "failed";

export interface FeatureConfigPayload {
  feature_name: string;
  feature_description: string;
  allowed_actions?: string;
  excluded_features?: string;
  coverage_level: CoverageLevel;
}

export interface BatchGenerateRequest {
  provider?: ApiProvider;
  model_profile?: "fast" | "smart" | "private";
  /** Model identifier; when set, provider is derived from it. */
  model_id?: ModelId;
  features: FeatureConfigPayload[];
}

export interface BatchGenerateResponse {
  batch_id: string;
}

export interface BatchFeatureResult {
  feature_id: string;
  feature_name: string;
  status: FeatureResultStatus;
  items?: TestCaseItem[] | null;
  error?: string | null;
}

export interface BatchStatusResponse {
  batch_id: string;
  status: "pending" | "running" | "completed" | "partial";
  features: BatchFeatureResult[];
}
