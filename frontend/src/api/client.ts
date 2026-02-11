/**
 * Dedicated API client for test case generation.
 * All backend calls go through this module; no fetch in components.
 */

import type {
  BatchGenerateRequest,
  BatchGenerateResponse,
  BatchStatusResponse,
  GenerateTestCasesRequest,
  TestCaseItem,
  TestCaseListResponse,
} from "./types";

/** Payload shape for export-to-excel: camelCase keys and testSteps as pipe-separated string. */
export interface ExportToExcelTestCase {
  testScenario: string;
  description: string;
  precondition: string;
  testData: string;
  testSteps: string;
  expectedResult: string;
}

export function itemToExportPayload(item: TestCaseItem): ExportToExcelTestCase {
  return {
    testScenario: item.test_scenario ?? "",
    description: item.test_description ?? "",
    precondition: item.pre_condition ?? "",
    testData: item.test_data ?? "",
    testSteps: Array.isArray(item.test_steps) ? item.test_steps.join(" | ") : String(item.test_steps ?? ""),
    expectedResult: item.expected_result ?? "",
  };
}

const getBaseUrl = (): string => {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (base) return base.replace(/\/$/, "");
  return ""; // use relative URLs when proxying (e.g. /api)
};

async function handleError(res: Response): Promise<never> {
  const body = await res.text();
  let message = `Request failed (${res.status})`;
  try {
    const json = JSON.parse(body);
    if (typeof json.detail === "string") message = json.detail;
    else if (Array.isArray(json.detail)) message = json.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ");
  } catch {
    if (body) message = body.slice(0, 200);
  }
  throw new Error(message);
}

export async function generateTestCases(
  payload: GenerateTestCasesRequest
): Promise<TestCaseListResponse> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/generate-test-cases`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) await handleError(res);
  return res.json();
}

// --- Batch ---

export async function batchGenerate(
  payload: BatchGenerateRequest
): Promise<BatchGenerateResponse> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/batch-generate`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await handleError(res);
  return res.json();
}

export async function getBatchStatus(
  batchId: string
): Promise<BatchStatusResponse> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/batches/${encodeURIComponent(batchId)}`;
  const res = await fetch(url);
  if (!res.ok) await handleError(res);
  return res.json();
}

export async function retryBatchFeature(
  batchId: string,
  featureId: string,
  provider?: string
): Promise<void> {
  const base = getBaseUrl();
  const q = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  const url = `${base}/api/testcases/batches/${encodeURIComponent(batchId)}/features/${encodeURIComponent(featureId)}/retry${q}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) await handleError(res);
}

/** Delete a test case. It is removed from the batch and excluded from all CSV exports. */
export async function deleteTestCase(testCaseId: string): Promise<void> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/${encodeURIComponent(testCaseId)}`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) await handleError(res);
}

/** Returns the URL to download merged (deduped) CSV for the batch. Backend sets filename via Content-Disposition. */
export function getBatchExportAllUrl(batchId: string): string {
  const base = getBaseUrl();
  return `${base}/api/testcases/batches/${encodeURIComponent(batchId)}/export-all`;
}

/** Get a unique OS-safe CSV filename from the backend (for single-feature export). */
export async function getCsvFilename(featureName?: string): Promise<string> {
  const base = getBaseUrl();
  const q = featureName != null && featureName !== "" ? `?feature_name=${encodeURIComponent(featureName)}` : "";
  const url = `${base}/api/testcases/csv-filename${q}`;
  const res = await fetch(url);
  if (!res.ok) await handleError(res);
  const json = (await res.json()) as { filename: string };
  return json.filename ?? "tc_export.csv";
}

/**
 * Export filtered test cases into an Excel template. Sends template file + JSON to backend,
 * then triggers download of the merged Excel file.
 */
export async function exportToExcelTemplate(
  templateFile: File,
  testCases: TestCaseItem[],
  featureName: string
): Promise<void> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/export-to-excel`;
  const form = new FormData();
  form.append("template", templateFile);
  form.append("testCases", JSON.stringify(testCases.map(itemToExportPayload)));
  form.append("featureName", featureName);

  const res = await fetch(url, {
    method: "POST",
    body: form,
  });
  if (!res.ok) await handleError(res);

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  let filename = `${featureName.replace(/[^\w\s-]/g, "_").replace(/\s+/g, "_")}_Test_Cases.xlsx`;
  if (disposition) {
    const match = /filename[*]?=(?:UTF-8'')?["']?([^"'\s;]+)["']?/.exec(disposition);
    if (match?.[1]) filename = match[1].trim();
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Payload for export-all: one entry per feature with test cases. */
export interface ExportAllFeaturePayload {
  featureName: string;
  testCases: ExportToExcelTestCase[];
}

/**
 * Export all features' test cases into one Excel template (one sheet per feature).
 */
export async function exportAllToExcelTemplate(
  templateFile: File,
  featuresData: ExportAllFeaturePayload[]
): Promise<void> {
  const base = getBaseUrl();
  const url = `${base}/api/testcases/export-all-to-excel`;
  const form = new FormData();
  form.append("template", templateFile);
  form.append("testCasesByFeature", JSON.stringify(featuresData));

  const res = await fetch(url, {
    method: "POST",
    body: form,
  });
  if (!res.ok) await handleError(res);

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  // Fallback filename if backend does not provide one; include local date + time (HHmm)
  // for uniqueness, e.g. All_Features_Test_Cases_2025-01-10_1432.xlsx.
  const now = new Date();
  const pad = (n: number) => n.toString().padStart(2, "0");
  const fallbackTimestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(
    now.getDate()
  )}_${pad(now.getHours())}${pad(now.getMinutes())}`;
  let filename = `All_Features_Test_Cases_${fallbackTimestamp}.xlsx`;
  if (disposition) {
    const match = /filename[*]?=(?:UTF-8'')?["']?([^"'\s;]+)["']?/.exec(disposition);
    if (match?.[1]) filename = match[1].trim();
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
