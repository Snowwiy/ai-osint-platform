export type NativeKnowledgePickerMode = "vault" | "documents";

interface NativeKnowledgePickerFile {
  relativeName: string;
  contentBase64: string;
  modifiedMs: number;
  sizeBytes: number;
}

export interface NativeKnowledgeSelection {
  files: File[];
  rootPath?: string;
  unsupportedCount: number;
  oversizedCount: number;
  totalBytes: number;
}

type TauriWindow = Window & {
  __TAURI__?: {
    core?: {
      invoke?: (command: string, args?: Record<string, unknown>) => Promise<unknown>;
    };
  };
};

export function nativeKnowledgePickerAvailable(): boolean {
  return typeof (window as TauriWindow).__TAURI__?.core?.invoke === "function";
}

export async function selectNativeKnowledgeFiles(
  mode: NativeKnowledgePickerMode,
): Promise<NativeKnowledgeSelection | null> {
  const invoke = (window as TauriWindow).__TAURI__?.core?.invoke;
  if (!invoke) throw new Error("The native desktop picker is unavailable.");
  const raw = await invoke("select_knowledge_files", { mode });
  if (raw === null) return null;
  if (!raw || typeof raw !== "object") throw new Error("The native picker returned an invalid selection.");
  const value = raw as Record<string, unknown>;
  if (!Array.isArray(value.files)) throw new Error("The native picker returned an invalid file list.");
  const files = value.files.map((entry): File => {
    if (!entry || typeof entry !== "object") throw new Error("The native picker returned an invalid file entry.");
    const selected = entry as NativeKnowledgePickerFile;
    if (
      typeof selected.relativeName !== "string" ||
      typeof selected.contentBase64 !== "string" ||
      !Number.isFinite(selected.modifiedMs) ||
      !Number.isSafeInteger(selected.sizeBytes) ||
      selected.sizeBytes < 0
    ) throw new Error("The native picker returned invalid document metadata.");
    const binary = atob(selected.contentBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    if (bytes.byteLength !== selected.sizeBytes) throw new Error("A selected document changed while it was being read.");
    const basename = selected.relativeName.split("/").pop() ?? selected.relativeName;
    const result = new File([bytes], basename, { lastModified: selected.modifiedMs });
    Object.defineProperty(result, "webkitRelativePath", { value: selected.relativeName });
    return result;
  });
  return {
    files,
    ...(typeof value.rootPath === "string" ? { rootPath: value.rootPath } : {}),
    unsupportedCount: Number(value.unsupportedCount ?? 0),
    oversizedCount: Number(value.oversizedCount ?? 0),
    totalBytes: Number(value.totalBytes ?? 0),
  };
}
