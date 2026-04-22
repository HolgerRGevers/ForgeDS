import JSZip from "jszip";
import type { DataAnalysis } from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

interface ParsedFile {
  filename: string;
  kind: "csv" | "ds" | "json" | "unsupported";
  preview: {
    columns?: string[];
    rows?: Array<Record<string, string>>;
    raw?: string;
  };
}

export async function parseAttachments(files: File[]): Promise<ParsedFile[]> {
  const out: ParsedFile[] = [];
  for (const f of files) {
    const lower = f.name.toLowerCase();
    if (lower.endsWith(".csv")) {
      out.push(await parseCsv(f));
    } else if (lower.endsWith(".zip")) {
      out.push(...(await parseZip(f)));
    } else if (lower.endsWith(".ds")) {
      out.push({
        filename: f.name,
        kind: "ds",
        preview: { raw: (await f.text()).slice(0, 5000) },
      });
    } else if (lower.endsWith(".json")) {
      out.push({
        filename: f.name,
        kind: "json",
        preview: { raw: (await f.text()).slice(0, 5000) },
      });
    } else if (lower.endsWith(".accdb")) {
      out.push({
        filename: f.name,
        kind: "unsupported",
        preview: {
          raw: "Access database files cannot be parsed in-browser. Please export tables to CSV.",
        },
      });
    }
  }
  return out;
}

async function parseCsv(file: File): Promise<ParsedFile> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const headerLine = lines[0] ?? "";
  const columns = splitCsvLine(headerLine);
  const rows = lines.slice(1, 51).map((line) => {
    const cells = splitCsvLine(line);
    const row: Record<string, string> = {};
    columns.forEach((c, i) => {
      row[c] = cells[i] ?? "";
    });
    return row;
  });
  return { filename: file.name, kind: "csv", preview: { columns, rows } };
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuote = false;
  for (const ch of line) {
    if (ch === '"') inQuote = !inQuote;
    else if (ch === "," && !inQuote) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

async function parseZip(file: File): Promise<ParsedFile[]> {
  const out: ParsedFile[] = [];
  const zip = await JSZip.loadAsync(file);
  for (const [name, entry] of Object.entries(zip.files)) {
    if (entry.dir) continue;
    if (name.toLowerCase().endsWith(".csv")) {
      const blob = await entry.async("blob");
      const inner = new File([blob], name);
      out.push(await parseCsv(inner));
    }
  }
  return out;
}

export async function analyzeData(
  token: string,
  parsed: ParsedFile[],
): Promise<DataAnalysis> {
  if (!CLAUDE_PROXY && parsed.length === 0) {
    return { entities: [], observedConstraints: [], gaps: ["No files to analyze"] };
  }
  const res = await fetch(`${CLAUDE_PROXY}/api/data-analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ parsed }),
  });
  if (!res.ok) throw new Error(`Data analysis failed (${res.status})`);
  return res.json();
}
