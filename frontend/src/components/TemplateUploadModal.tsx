import React, { useCallback, useRef, useState } from "react";
import { FileSpreadsheet, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { storedTemplateToFile, type StoredTemplate } from "@/hooks/useTemplateStorage";

const ACCEPT = ".xlsx";
const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export interface TemplateUploadModalProps {
  open: boolean;
  onClose: () => void;
  onExport: (file: File, remember: boolean) => void | Promise<void>;
  isLoading?: boolean;
  /** When set, show "Using template: filename" and Export uses this template. */
  storedTemplate?: StoredTemplate | null;
  onClearTemplate?: () => void;
  /** Override modal title (e.g. "Export All Features to Excel Template"). */
  title?: string;
  /** Override description (e.g. "This will create one Excel file with X sheets (one per feature)."). */
  description?: string;
  className?: string;
}

export function TemplateUploadModal({
  open,
  onClose,
  onExport,
  isLoading = false,
  storedTemplate = null,
  onClearTemplate,
  title: titleProp,
  description: descriptionProp,
  className,
}: TemplateUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSet = useCallback((f: File | null) => {
    setError(null);
    if (!f) {
      setFile(null);
      return;
    }
    const name = f.name.toLowerCase();
    if (!name.endsWith(".xlsx")) {
      setError("Only .xlsx files are allowed.");
      setFile(null);
      return;
    }
    if (f.size > MAX_SIZE_BYTES) {
      setError(`File must be under ${MAX_SIZE_MB}MB.`);
      setFile(null);
      return;
    }
    setFile(f);
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const chosen = e.target.files?.[0] ?? null;
      validateAndSet(chosen);
    },
    [validateAndSet]
  );

  const handleExport = useCallback(async () => {
    const fileToUse = storedTemplate ? storedTemplateToFile(storedTemplate) : file;
    if (!fileToUse) {
      setError("Please select an Excel template (.xlsx).");
      return;
    }
    try {
      await onExport(fileToUse, remember);
      onClose();
      setFile(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  }, [storedTemplate, file, remember, onExport, onClose]);

  const handleClose = useCallback(() => {
    if (isLoading) return;
    onClose();
    setFile(null);
    setError(null);
  }, [onClose, isLoading]);

  if (!open) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
        className
      )}
      role="dialog"
      aria-modal="true"
      aria-labelledby="template-modal-title"
    >
      <div
        className="absolute inset-0"
        onClick={handleClose}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-md rounded-xl border border-neutral-200 bg-white p-6 shadow-lg dark:border-neutral-700 dark:bg-neutral-800">
        <h2
          id="template-modal-title"
          className="flex items-center gap-2 text-lg font-semibold text-neutral-900 dark:text-neutral-100"
        >
          <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
          {titleProp ?? "Export to Excel Template"}
        </h2>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
          {descriptionProp ?? "Upload an Excel template (.xlsx). Test cases will be merged into the \"Test Cases\" sheet."}
        </p>

        {storedTemplate ? (
          <div className="mt-4 rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-700 dark:bg-neutral-800/50">
            <p className="text-sm text-neutral-700 dark:text-neutral-300">
              Using template: <span className="font-medium">{storedTemplate.filename}</span>
            </p>
            {onClearTemplate && (
              <button
                type="button"
                onClick={onClearTemplate}
                className="mt-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
              >
                Change template
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="mt-4">
              <Label htmlFor="template-file">Template file (.xlsx)</Label>
              <Input
                id="template-file"
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                onChange={handleFileChange}
                className="mt-1"
              />
              {file && (
                <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                  Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>
            <div className="mt-4 flex items-center gap-2">
              <input
                id="remember-template"
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-500 dark:border-neutral-600 dark:bg-neutral-700"
              />
              <Label htmlFor="remember-template" className="font-normal">
                Remember this template
              </Label>
            </div>
          </>
        )}

        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleExport} disabled={isLoading || (!storedTemplate && !file)}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Exporting…
              </>
            ) : (
              "Export"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
