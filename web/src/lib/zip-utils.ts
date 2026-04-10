import JSZip from "jszip";

export type FileCategory = "document" | "image" | "data" | "code" | "config" | "other";

export interface ExtractedFile {
  path: string;
  name: string;
  content: string;
  isBinary: boolean;
  size: number;
  targetPath: string;
  category: FileCategory;
}

const CATEGORY_MAP: Record<string, FileCategory> = {
  // Documents
  ".pdf": "document", ".doc": "document", ".docx": "document",
  ".txt": "document", ".md": "document", ".rtf": "document",
  // Images
  ".png": "image", ".jpg": "image", ".jpeg": "image",
  ".gif": "image", ".svg": "image", ".webp": "image", ".ico": "image",
  // Data
  ".csv": "data", ".json": "data", ".yaml": "data",
  ".yml": "data", ".xml": "data", ".xlsx": "data", ".xls": "data",
  // Code
  ".py": "code", ".js": "code", ".ts": "code", ".tsx": "code",
  ".jsx": "code", ".sql": "code", ".ds": "code", ".dg": "code",
  ".html": "code", ".css": "code", ".java": "code", ".go": "code",
  ".rs": "code", ".rb": "code", ".php": "code", ".sh": "code",
  // Config
  ".env": "config", ".gitignore": "config", ".editorconfig": "config",
  ".toml": "config", ".ini": "config", ".cfg": "config",
};

const BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
  ".pdf", ".doc", ".docx", ".xlsx", ".xls", ".rtf",
  ".zip", ".tar", ".gz",
]);

const DIR_MAP: Record<FileCategory, string> = {
  document: "docs",
  image: "assets/images",
  data: "data",
  code: "src",
  config: "",
  other: "resources",
};

export function categorizeFile(filename: string): FileCategory {
  const lower = filename.toLowerCase();
  const ext = lower.substring(lower.lastIndexOf("."));
  return CATEGORY_MAP[ext] ?? "other";
}

function isBinaryFile(filename: string): boolean {
  const lower = filename.toLowerCase();
  const ext = lower.substring(lower.lastIndexOf("."));
  return BINARY_EXTENSIONS.has(ext);
}

export function computeTargetPath(filename: string, category: FileCategory): string {
  const dir = DIR_MAP[category];
  return dir ? `${dir}/${filename}` : filename;
}

function stripCommonRoot(paths: string[]): string {
  if (paths.length === 0) return "";
  const parts = paths[0].split("/");
  if (parts.length <= 1) return "";

  let prefix = parts[0];
  for (const p of paths) {
    if (!p.startsWith(prefix + "/")) return "";
  }
  return prefix + "/";
}

const MAX_ZIP_SIZE = 50 * 1024 * 1024; // 50 MB

export async function extractZip(file: File): Promise<ExtractedFile[]> {
  if (file.size > MAX_ZIP_SIZE) {
    throw new Error("ZIP file exceeds 50 MB limit");
  }

  const zip = await JSZip.loadAsync(file);
  const entries: Array<{ path: string; zipEntry: JSZip.JSZipObject }> = [];

  zip.forEach((relativePath, zipEntry) => {
    if (!zipEntry.dir) {
      entries.push({ path: relativePath, zipEntry });
    }
  });

  // Strip common root folder (e.g., "project-v1/...")
  const allPaths = entries.map((e) => e.path);
  const commonRoot = stripCommonRoot(allPaths);

  const results: ExtractedFile[] = [];

  for (const entry of entries) {
    const strippedPath = commonRoot ? entry.path.slice(commonRoot.length) : entry.path;
    if (!strippedPath) continue;

    const name = strippedPath.split("/").pop() ?? strippedPath;
    const binary = isBinaryFile(name);
    const category = categorizeFile(name);
    const targetPath = computeTargetPath(name, category);

    let content: string;
    let size: number;

    if (binary) {
      const uint8 = await entry.zipEntry.async("uint8array");
      size = uint8.length;
      content = await entry.zipEntry.async("base64");
    } else {
      const text = await entry.zipEntry.async("string");
      size = new Blob([text]).size;
      content = text;
    }

    results.push({ path: strippedPath, name, content, isBinary: binary, size, targetPath, category });
  }

  return results;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
