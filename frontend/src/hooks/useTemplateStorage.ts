/**
 * Store/retrieve Excel template in localStorage as base64.
 * Key: export_excel_template
 * Value: JSON { filename: string, base64: string }
 */
const STORAGE_KEY = "export_excel_template";

export interface StoredTemplate {
  filename: string;
  base64: string;
}

export function getStoredTemplate(): StoredTemplate | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      "filename" in parsed &&
      "base64" in parsed &&
      typeof (parsed as StoredTemplate).filename === "string" &&
      typeof (parsed as StoredTemplate).base64 === "string"
    ) {
      return parsed as StoredTemplate;
    }
  } catch {
    // ignore
  }
  return null;
}

export function setStoredTemplate(filename: string, base64: string): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ filename, base64 }));
}

export function clearStoredTemplate(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** Convert File to base64 string. */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        const base64 = result.replace(/^data:[^;]+;base64,/, "");
        resolve(base64);
      } else {
        reject(new Error("Failed to read file as data URL"));
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Convert stored base64 + filename back to a File (for sending to API). */
export function storedTemplateToFile(stored: StoredTemplate): File {
  const binary = atob(stored.base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], stored.filename, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}
