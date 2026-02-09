import { useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Circle,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResultsTable, exportToCsv } from "@/components/ResultsTable";
import { TemplateUploadModal } from "@/components/TemplateUploadModal";
import type { BatchFeatureResult, BatchStatusResponse, TestCaseItem } from "@/api/types";
import {
  deleteTestCase,
  exportAllToExcelTemplate,
  exportToExcelTemplate,
  getBatchExportAllUrl,
  getCsvFilename,
  itemToExportPayload,
} from "@/api/client";
import type { ExportAllFeaturePayload } from "@/api/client";
import {
  clearStoredTemplate,
  fileToBase64,
  getStoredTemplate,
  setStoredTemplate,
} from "@/hooks/useTemplateStorage";

function StatusIcon({ status }: { status: BatchFeatureResult["status"] }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case "failed":
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    case "generating":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    default:
      return <Circle className="h-4 w-4 text-neutral-400" />;
  }
}

interface BatchResultsViewProps {
  batch: BatchStatusResponse;
  onRetry: (featureId: string) => Promise<void>;
  onBatchRefresh?: () => Promise<void>;
  onExportAll?: () => void;
  className?: string;
}

export function BatchResultsView({
  batch,
  onRetry,
  onBatchRefresh,
  onExportAll,
  className = "",
}: BatchResultsViewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [excelModalFeature, setExcelModalFeature] = useState<BatchFeatureResult | null>(null);
  const [excelModalExportAll, setExcelModalExportAll] = useState(false);
  const [excelExporting, setExcelExporting] = useState(false);
  const [excelStoredTemplate, setExcelStoredTemplate] = useState<ReturnType<typeof getStoredTemplate>>(null);

  const toggle = useCallback((featureId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(featureId)) next.delete(featureId);
      else next.add(featureId);
      return next;
    });
  }, []);

  const handleExportFeature = useCallback(async (fr: BatchFeatureResult) => {
    const items = fr.items ?? [];
    if (items.length === 0) return;
    const filename = await getCsvFilename(fr.feature_name);
    exportToCsv(items, filename);
  }, []);

  const handleExportAll = useCallback(() => {
    const url = getBatchExportAllUrl(batch.batch_id);
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    a.click();
    onExportAll?.();
  }, [batch.batch_id, onExportAll]);

  const handleDeleteTestCase = useCallback(
    async (testCaseId: string) => {
      await deleteTestCase(testCaseId);
      await onBatchRefresh?.();
    },
    [onBatchRefresh]
  );

  const handleExportToExcel = useCallback(
    async (file: File, remember: boolean) => {
      setExcelExporting(true);
      try {
        if (excelModalExportAll) {
          const featuresWithItems = batch.features.filter(
            (f) => (f.items?.length ?? 0) > 0
          );
          if (featuresWithItems.length === 0) return;
          const featuresData: ExportAllFeaturePayload[] = featuresWithItems.map(
            (f) => ({
              featureName: f.feature_name,
              testCases: (f.items ?? []).map((tc) =>
                itemToExportPayload(tc as TestCaseItem)
              ),
            })
          );
          await exportAllToExcelTemplate(file, featuresData);
        } else {
          if (!excelModalFeature) return;
          const items = (excelModalFeature.items ?? []) as TestCaseItem[];
          if (items.length === 0) return;
          await exportToExcelTemplate(file, items, excelModalFeature.feature_name);
        }
        if (remember) {
          const base64 = await fileToBase64(file);
          setStoredTemplate(file.name, base64);
        }
      } finally {
        setExcelExporting(false);
      }
    },
    [excelModalExportAll, excelModalFeature, batch.features]
  );

  const totalItems = batch.features.reduce(
    (sum, f) => sum + (f.items?.length ?? 0),
    0
  );
  const hasAnyResults = totalItems > 0;

  return (
    <div className={`flex flex-col h-full min-h-0 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 shrink-0">
        <div className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
          <span>
            Batch: {batch.status}
            {batch.features.length > 0 && (
              <> · {batch.features.length} feature{batch.features.length !== 1 ? "s" : ""}</>
            )}
            {totalItems > 0 && <> · {totalItems} test case{totalItems !== 1 ? "s" : ""}</>}
          </span>
        </div>
        {hasAnyResults && (
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportAll}
              className="shrink-0"
            >
              <Download className="h-4 w-4" />
              Export All Features
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setExcelModalExportAll(true);
                setExcelModalFeature(null);
                setExcelStoredTemplate(getStoredTemplate());
              }}
              className="shrink-0"
            >
              <FileSpreadsheet className="h-4 w-4" />
              Export All to Excel Template
            </Button>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-auto space-y-2">
        {batch.features.map((fr) => {
          const isExpanded = expandedIds.has(fr.feature_id);
          const items = (fr.items ?? []) as TestCaseItem[];
          const canExport = items.length > 0;

          return (
            <div
              key={fr.feature_id}
              className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800/50 overflow-hidden"
            >
              <div className="flex items-center gap-2 p-3 bg-neutral-50/80 dark:bg-neutral-800/80 border-b border-neutral-200 dark:border-neutral-700">
                <button
                  type="button"
                  onClick={() => toggle(fr.feature_id)}
                  className="flex items-center gap-2 min-w-0 flex-1 text-left"
                  aria-expanded={isExpanded}
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 shrink-0 text-neutral-500" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0 text-neutral-500" />
                  )}
                  <StatusIcon status={fr.status} />
                  <span className="font-medium text-neutral-900 dark:text-neutral-100 truncate">
                    {fr.feature_name}
                  </span>
                  {items.length > 0 && (
                    <span className="text-xs text-neutral-500 dark:text-neutral-400">
                      {items.length} case{items.length !== 1 ? "s" : ""}
                    </span>
                  )}
                </button>
                <div className="flex items-center gap-2 shrink-0">
                  {canExport && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleExportFeature(fr)}
                        className="h-8"
                      >
                        <Download className="h-4 w-4" />
                        Export CSV
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setExcelModalFeature(fr);
                          setExcelModalExportAll(false);
                          setExcelStoredTemplate(getStoredTemplate());
                        }}
                        className="h-8"
                      >
                        <FileSpreadsheet className="h-4 w-4" />
                        Export to Excel Template
                      </Button>
                    </>
                  )}
                  {fr.status === "failed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        setRetryingId(fr.feature_id);
                        try {
                          await onRetry(fr.feature_id);
                        } finally {
                          setRetryingId(null);
                        }
                      }}
                      disabled={retryingId !== null}
                      className="h-8"
                    >
                      {retryingId === fr.feature_id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4" />
                      )}
                      Retry
                    </Button>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="p-3">
                  {fr.status === "failed" && fr.error && (
                    <p className="text-sm text-red-600 dark:text-red-400 mb-3">
                      {fr.error}
                    </p>
                  )}
                  {items.length > 0 ? (
                    <ResultsTable
                      items={items}
                      onExportCsv={() => handleExportFeature(fr)}
                      onDeleteTestCase={onBatchRefresh ? handleDeleteTestCase : undefined}
                      className="border-0 rounded-lg"
                    />
                  ) : (
                    <div className="py-6 text-center text-sm text-neutral-500 dark:text-neutral-400">
                      {fr.status === "pending" && "Waiting to start…"}
                      {fr.status === "generating" && "Generating…"}
                      {fr.status === "failed" && "No results. Use Retry to try again."}
                      {fr.status === "completed" && "No test cases generated."}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <TemplateUploadModal
        open={excelModalFeature !== null || excelModalExportAll}
        onClose={() => {
          setExcelModalFeature(null);
          setExcelModalExportAll(false);
        }}
        onExport={handleExportToExcel}
        isLoading={excelExporting}
        storedTemplate={excelStoredTemplate}
        onClearTemplate={() => {
          clearStoredTemplate();
          setExcelStoredTemplate(null);
        }}
        title={excelModalExportAll ? "Export All Features to Excel Template" : undefined}
        description={
          excelModalExportAll
            ? `This will create one Excel file with ${batch.features.filter((f) => (f.items?.length ?? 0) > 0).length} sheet${batch.features.filter((f) => (f.items?.length ?? 0) > 0).length === 1 ? "" : "s"} (one per feature).`
            : undefined
        }
      />
    </div>
  );
}
