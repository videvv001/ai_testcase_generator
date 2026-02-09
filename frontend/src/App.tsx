import { useState, useCallback, useEffect, useRef } from "react";
import {
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeft,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { GenerationForm, type BatchFormValues, type SingleFeatureValues } from "@/components/GenerationForm";
import { ResultsTableSkeleton } from "@/components/ResultsTableSkeleton";
import { BatchResultsView } from "@/components/BatchResultsView";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { batchGenerate, getBatchStatus, retryBatchFeature } from "@/api/client";
import type { BatchStatusResponse } from "@/api/types";

const THEME_KEY = "ai-tc-gen-theme";
const PANEL_KEY = "ai-tc-gen-panel-collapsed";
const POLL_INTERVAL_MS = 1500;

function getStoredTheme(): "light" | "dark" {
  try {
    const s = localStorage.getItem(THEME_KEY);
    if (s === "dark" || s === "light") return s;
  } catch {}
  return "light";
}

function getStoredPanelCollapsed(): boolean {
  try {
    return localStorage.getItem(PANEL_KEY) === "true";
  } catch {}
  return false;
}

function modelIdToProvider(modelId: string): "ollama" | "openai" | "gemini" | "groq" {
  if (modelId === "gpt-4o-mini" || modelId === "gpt-4o") return "openai";
  if (modelId === "gemini-2.5-flash") return "gemini";
  if (modelId === "llama-3.3-70b-versatile") return "groq";
  return "ollama";
}

function buildFeatureDescription(f: SingleFeatureValues): string {
  let text = f.featureDescription.trim();
  const allowed = f.allowedActions
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const excluded = f.excludedFeatures
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (allowed.length > 0) {
    text += "\n\nAllowed actions: " + allowed.join(", ");
  }
  if (excluded.length > 0) {
    text += "\n\nExcluded features: " + excluded.join(", ");
  }
  return text;
}

export default function App() {
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchStatusResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastValues, setLastValues] = useState<BatchFormValues | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(getStoredTheme);
  const [panelCollapsed, setPanelCollapsed] = useState(getStoredPanelCollapsed);
  const [resultsFullscreen, setResultsFullscreen] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isGenerating =
    isSubmitting ||
    (batch !== null &&
      (batch.status === "pending" || batch.status === "running"));

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {}
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_KEY, String(panelCollapsed));
    } catch {}
  }, [panelCollapsed]);

  const runGeneration = useCallback(async (values: BatchFormValues) => {
    setError(null);
    setLastValues(values);
    setIsSubmitting(true);
    setBatch(null);
    setBatchId(null);
    try {
      const features = values.features.map((f) => ({
        feature_name: f.featureName.trim(),
        feature_description: buildFeatureDescription(f),
        allowed_actions: f.allowedActions.trim() || undefined,
        excluded_features: f.excludedFeatures.trim() || undefined,
        coverage_level: f.coverageLevel,
      }));
      const res = await batchGenerate({
        model_id: values.modelId,
        features,
      });
      setBatchId(res.batch_id);
      const initial = await getBatchStatus(res.batch_id);
      setBatch(initial);
    } catch (e) {
      const message =
        e instanceof Error
          ? e.message
          : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  useEffect(() => {
    if (!batchId || !batch) return;
    if (batch.status !== "pending" && batch.status !== "running") return;

    pollRef.current = setInterval(async () => {
      try {
        const next = await getBatchStatus(batchId);
        setBatch(next);
        if (next.status !== "pending" && next.status !== "running") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        // keep polling on transient errors
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [batchId, batch?.status]);

  const handleRetryFeature = useCallback(
    async (featureId: string) => {
      if (!batchId || !batch) return;
      const provider = lastValues
        ? modelIdToProvider(lastValues.modelId)
        : undefined;
      await retryBatchFeature(batchId, featureId, provider);
      const updated = await getBatchStatus(batchId);
      setBatch(updated);
    },
    [batchId, batch, lastValues]
  );

  const handleBatchRefresh = useCallback(async () => {
    if (!batchId) return;
    const updated = await getBatchStatus(batchId);
    setBatch(updated);
  }, [batchId]);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50 dark:bg-neutral-900">
      <header className="border-b border-neutral-200 bg-white px-4 py-3 dark:border-neutral-700 dark:bg-neutral-800 shrink-0">
        <div className="flex items-center justify-between gap-4 max-w-[1800px] mx-auto">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPanelCollapsed((c) => !c)}
              title={
                panelCollapsed
                  ? "Expand configuration"
                  : "Collapse configuration"
              }
              className="shrink-0 text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
            >
              {panelCollapsed ? (
                <PanelLeft className="h-5 w-5" />
              ) : (
                <PanelLeftClose className="h-5 w-5" />
              )}
            </Button>
            <div className="min-w-0">
              <h1 className="text-base font-semibold text-neutral-900 dark:text-neutral-50 truncate">
                AI Test Case Generator
              </h1>
              <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">
                Configure parameters and generate test cases.
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() =>
              setTheme((t) => (t === "light" ? "dark" : "light"))
            }
            title={
              theme === "light"
                ? "Switch to dark mode"
                : "Switch to light mode"
            }
            className="shrink-0 text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
          >
            {theme === "light" ? (
              <Moon className="h-5 w-5" />
            ) : (
              <Sun className="h-5 w-5" />
            )}
          </Button>
        </div>
      </header>

      <main className="flex-1 flex min-h-0">
        <aside
          className={`
            shrink-0 overflow-hidden border-r border-neutral-200 dark:border-neutral-700
            bg-white dark:bg-neutral-800/50
            transition-[width] duration-300 ease-out
            ${panelCollapsed ? "w-0 border-r-0" : "w-[360px] lg:w-[30%] xl:max-w-[420px]"}
          `}
        >
          <div className="h-full overflow-y-auto p-4 w-[360px] lg:w-full">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50/50 dark:bg-neutral-800/30 p-4">
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                Configuration
              </h2>
              <GenerationForm
                isGenerating={isGenerating}
                onSubmit={runGeneration}
              />
            </div>
          </div>
        </aside>

        <section
          className={`
            flex-1 flex flex-col min-w-0
            transition-[max-width] duration-300 ease-out
            ${
              resultsFullscreen
                ? "fixed top-14 left-0 right-0 bottom-0 z-40 bg-neutral-50 dark:bg-neutral-900"
                : ""
            }
          `}
        >
          <div className="flex-1 flex flex-col min-h-0 p-4 max-w-[1800px] w-full mx-auto">
            <div className="flex items-center justify-between gap-4 mb-3 shrink-0">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-50">
                Test Case Results
              </h2>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setResultsFullscreen((f) => !f)}
                  title={
                    resultsFullscreen ? "Exit fullscreen" : "Fullscreen"
                  }
                  className="shrink-0 text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
                >
                  {resultsFullscreen ? (
                    <Minimize2 className="h-4 w-4" />
                  ) : (
                    <Maximize2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-4 rounded-xl">
                <AlertTitle>Generation failed</AlertTitle>
                <AlertDescription className="mt-2 flex flex-wrap items-center gap-2">
                  <span>{error}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setError(null)}
                    className="border-red-200 bg-white text-red-800 hover:bg-red-50 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200 dark:hover:bg-red-950/50"
                  >
                    Dismiss
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setError(null);
                      if (lastValues) runGeneration(lastValues);
                    }}
                  >
                    Retry
                  </Button>
                </AlertDescription>
              </Alert>
            )}

            <div className="flex-1 min-h-0 overflow-hidden">
              {isGenerating && !batch ? (
                <ResultsTableSkeleton />
              ) : batch ? (
                <BatchResultsView
                  batch={batch}
                  onRetry={handleRetryFeature}
                  onBatchRefresh={handleBatchRefresh}
                  className="animate-fade-in"
                />
              ) : (
                <div className="flex flex-col items-center justify-center rounded-xl border border-neutral-200 bg-neutral-50/50 dark:border-neutral-700 dark:bg-neutral-800/30 py-16 text-center text-neutral-500 dark:text-neutral-400">
                  <p className="text-sm">No batch yet.</p>
                  <p className="mt-1 text-xs">
                    Add one or more features and click Generate Test Cases.
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
