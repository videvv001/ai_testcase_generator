/**
 * Stable export column contract. Do NOT derive from API response keys.
 * Column order and names must remain fixed for consistent CSV/Excel consumption.
 * If the backend adds new fields, ignore them unless explicitly added here.
 */

export const EXPORT_COLUMNS = [
  "Test Scenario",
  "Description",
  "Precondition",
  "Test Data",
  "Test Steps",
  "Expected Result",
] as const;

export type ExportColumnName = (typeof EXPORT_COLUMNS)[number];

/** Item shape for export only. Maps one test case to the fixed column order. */
export interface ExportRow {
  "Test Scenario": string;
  "Description": string;
  "Precondition": string;
  "Test Data": string;
  "Test Steps": string;
  "Expected Result": string;
}

export type ExportRowTuple = readonly [
  string,
  string,
  string,
  string,
  string,
  string,
];
