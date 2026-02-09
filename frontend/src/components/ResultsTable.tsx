import React, { useState, useCallback } from "react";
import { ChevronDown, ChevronRight, Download, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TestCaseItem } from "@/api/types";
import { EXPORT_COLUMNS } from "@/constants/exportColumns";

interface ResultsTableProps {
  items: TestCaseItem[];
  onExportCsv: () => void;
  onDeleteTestCase?: (testCaseId: string) => void | Promise<void>;
  className?: string;
}

/** Renders steps as-is; backend often includes numbering (e.g. "1. Enter username"). */
function StepsList({ steps }: { steps: string[] }) {
  return (
    <div className="space-y-0.5 text-[13px] leading-snug text-neutral-700 dark:text-neutral-300">
      {steps.map((step, i) => (
        <div key={i} className="whitespace-normal break-words">
          {step}
        </div>
      ))}
    </div>
  );
}

/** Map one test case to the stable export row. Only EXPORT_COLUMNS fields; ignore any extra API keys. */
function itemToExportRow(tc: TestCaseItem): string[] {
  return [
    tc.test_scenario,
    tc.test_description,
    tc.pre_condition,
    tc.test_data,
    tc.test_steps.join(" | "),
    tc.expected_result,
  ];
}

/** Export items to CSV; optional filename (default "test-cases.csv"). */
export function exportToCsv(items: TestCaseItem[], filename = "test-cases.csv"): void {
  const escape = (s: string) => {
    const t = String(s ?? "").replace(/"/g, '""');
    return t.includes(",") || t.includes('"') || t.includes("\n") ? `"${t}"` : t;
  };
  const headerRow = [...EXPORT_COLUMNS].join(",");
  const dataRows = items.map((tc) => itemToExportRow(tc).map(escape).join(","));
  const csv = headerRow + "\n" + dataRows.join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ResultsTable({ items, onExportCsv, onDeleteTestCase, className = "" }: ResultsTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const toggle = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  const handleExport = useCallback(() => {
    onExportCsv();
  }, [onExportCsv]);

  const handleDelete = useCallback(
    async (id: string) => {
      if (!onDeleteTestCase) return;
      setDeletingId(id);
      try {
        await onDeleteTestCase(id);
      } finally {
        setDeletingId(null);
      }
    },
    [onDeleteTestCase]
  );

  if (items.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center rounded-xl border border-neutral-200 bg-neutral-50/50 py-16 text-center text-neutral-500 dark:border-neutral-700 dark:bg-neutral-800/30 dark:text-neutral-400 ${className}`}
      >
        <p className="text-sm">No test cases yet.</p>
        <p className="mt-1 text-xs">Configure options and generate to see results here.</p>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full min-h-0 ${className}`}>
      <div className="flex items-center justify-between gap-4 mb-3 shrink-0">
        <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
          {items.length} test case{items.length !== 1 ? "s" : ""}
        </p>
        <Button variant="outline" size="sm" onClick={handleExport} className="shrink-0">
          <Download className="h-4 w-4" />
          Export to CSV
        </Button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto rounded-xl border border-neutral-200 dark:border-neutral-700">
        <table className="w-full min-w-[900px] border-collapse text-left text-[13px]">
          <thead className="sticky top-0 z-10 bg-neutral-50 dark:bg-neutral-800/95 shadow-[0_1px_0_0_rgba(0,0,0,0.05)] dark:shadow-[0_1px_0_0_rgba(255,255,255,0.05)]">
            <tr className="border-b border-neutral-200 dark:border-neutral-600">
              <th className="w-9 shrink-0 p-2 text-neutral-600 dark:text-neutral-400" aria-label="Expand" />
              {onDeleteTestCase ? (
                <th className="w-9 shrink-0 p-2 text-neutral-600 dark:text-neutral-400" aria-label="Delete" />
              ) : null}
              <th className="min-w-[140px] w-[16%] p-2.5 font-medium text-neutral-700 dark:text-neutral-300">
                Scenario
              </th>
              <th className="min-w-[160px] w-[20%] p-2.5 font-medium text-neutral-700 dark:text-neutral-300">
                Description
              </th>
              <th className="min-w-[120px] w-[16%] p-2.5 font-medium text-neutral-700 dark:text-neutral-300">
                Preconditions
              </th>
              <th className="min-w-[200px] w-[24%] p-2.5 font-medium text-neutral-700 dark:text-neutral-300">
                Test Steps
              </th>
              <th className="min-w-[120px] w-[14%] p-2.5 font-medium text-neutral-700 dark:text-neutral-300">
                Expected Result
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((tc) => {
              const isExpanded = expandedId === tc.id;
              return (
                <React.Fragment key={tc.id}>
                  <tr className="border-b border-neutral-100 transition-colors hover:bg-neutral-50/60 dark:border-neutral-700/50 dark:hover:bg-neutral-800/40">
                    <td className="p-2 align-top">
                      <button
                        type="button"
                        onClick={() => toggle(tc.id)}
                        className="rounded p-1 text-neutral-500 hover:bg-neutral-200 hover:text-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-600 dark:hover:text-neutral-200 transition-colors"
                        aria-expanded={isExpanded}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </button>
                    </td>
                    {onDeleteTestCase ? (
                      <td className="p-2 align-top">
                        <button
                          type="button"
                          onClick={() => handleDelete(tc.id)}
                          disabled={deletingId === tc.id}
                          className="rounded p-1 text-neutral-500 hover:bg-red-100 hover:text-red-600 dark:text-neutral-400 dark:hover:bg-red-900/40 dark:hover:text-red-400 transition-colors disabled:opacity-50"
                          title="Delete test case (excluded from CSV export)"
                          aria-label="Delete test case"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    ) : null}
                    <td className="p-2.5 align-top font-medium text-neutral-900 dark:text-neutral-100">
                      <span className="block whitespace-normal break-words">{tc.test_scenario}</span>
                    </td>
                    <td className="p-2.5 align-top text-neutral-700 dark:text-neutral-300">
                      <span className="block whitespace-normal break-words">{tc.test_description}</span>
                    </td>
                    <td className="p-2.5 align-top text-neutral-700 dark:text-neutral-300">
                      <span className="block whitespace-normal break-words">{tc.pre_condition}</span>
                    </td>
                    <td className="p-2.5 align-top text-neutral-700 dark:text-neutral-300">
                      <StepsList steps={tc.test_steps} />
                    </td>
                    <td className="p-2.5 align-top text-neutral-700 dark:text-neutral-300">
                      <span className="block whitespace-normal break-words">{tc.expected_result}</span>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="border-b border-neutral-100 bg-neutral-50/40 dark:border-neutral-700/50 dark:bg-neutral-800/30">
                      <td className="p-2" />
                      {onDeleteTestCase ? <td className="p-2" /> : null}
                      <td colSpan={5} className="p-4">
                        <div className="grid gap-4 text-[13px] sm:grid-cols-2">
                          <div>
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Scenario
                            </p>
                            <p className="whitespace-pre-wrap break-words text-neutral-800 dark:text-neutral-200">
                              {tc.test_scenario}
                            </p>
                          </div>
                          <div>
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Description
                            </p>
                            <p className="whitespace-pre-wrap break-words text-neutral-800 dark:text-neutral-200">
                              {tc.test_description}
                            </p>
                          </div>
                          <div>
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Preconditions
                            </p>
                            <p className="whitespace-pre-wrap break-words text-neutral-800 dark:text-neutral-200">
                              {tc.pre_condition}
                            </p>
                          </div>
                          <div>
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Test Data
                            </p>
                            <p className="whitespace-pre-wrap break-words text-neutral-800 dark:text-neutral-200">
                              {tc.test_data}
                            </p>
                          </div>
                          <div className="sm:col-span-2">
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Test Steps
                            </p>
                            <StepsList steps={tc.test_steps} />
                          </div>
                          <div className="sm:col-span-2">
                            <p className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
                              Expected Result
                            </p>
                            <p className="whitespace-pre-wrap break-words text-neutral-800 dark:text-neutral-200">
                              {tc.expected_result}
                            </p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
