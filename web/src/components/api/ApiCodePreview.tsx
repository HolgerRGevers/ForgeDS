import { useCallback, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { useDelugeLanguage } from "../../hooks/useMonaco";
import { DELUGE_THEME } from "../../lib/deluge-language";
import { useApiStore } from "../../stores/apiStore";
import type { CustomApiDefinition } from "../../types/api";

/* ------------------------------------------------------------------ */
/*  Code generation                                                    */
/* ------------------------------------------------------------------ */

function generateDelugeCode(draft: CustomApiDefinition): string {
  const funcName = draft.functionName || "untitled_function";

  // Build typed parameter list
  const paramArgs = draft.parameters
    .filter((p) => p.key.trim())
    .map((p) => {
      const typeMap: Record<string, string> = {
        text: "text",
        number: "number",
        date: "date",
        boolean: "boolean",
      };
      return `${typeMap[p.type] ?? "text"} ${p.key}`;
    })
    .join(", ");

  // Build parameter comment lines
  const paramComments = draft.parameters
    .filter((p) => p.key.trim())
    .map(
      (p) =>
        `    // Parameter: ${p.key} (${p.type})${p.description ? ` - ${p.description}` : ""}`,
    )
    .join("\n");

  // Build return block based on response type
  let returnBlock: string;
  if (
    draft.responseType === "custom" &&
    draft.statusCodes.length > 0
  ) {
    const statusLines = draft.statusCodes
      .map(
        (sc) =>
          `    // Status ${sc.statusCode} -> Response Code ${sc.responseCode}`,
      )
      .join("\n");
    returnBlock = [
      `    // Custom status code mappings:`,
      statusLines,
      `    response.put("status", "success");`,
      `    response.put("code", "${draft.statusCodes[0].responseCode}");`,
      `    return response;`,
    ].join("\n");
  } else {
    returnBlock = [
      `    response.put("status", "success");`,
      `    response.put("code", "3000");`,
      `    return response;`,
    ].join("\n");
  }

  const authLabel = draft.auth === "oauth2" ? "OAuth2" : "Public Key";
  const scopeLabel = draft.userScope.replace(/_/g, " ");

  const lines = [
    `map ${funcName}(${paramArgs})`,
    `{`,
    `    response = Map();`,
    ``,
    `    // TODO: Implement ${draft.name || funcName} logic`,
    `    // Method: ${draft.method}`,
    `    // Auth: ${authLabel}`,
    `    // Scope: ${scopeLabel}`,
    ``,
  ];

  if (paramComments) {
    lines.push(paramComments);
    lines.push(``);
  }

  lines.push(returnBlock);
  lines.push(`}`);

  return lines.join("\n");
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ApiCodePreview() {
  useDelugeLanguage();

  const draftApi = useApiStore((s) => s.draftApi);
  const [copied, setCopied] = useState(false);

  const code = useMemo(
    () => (draftApi ? generateDelugeCode(draftApi) : ""),
    [draftApi],
  );

  const handleCopy = useCallback(async () => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may be unavailable
    }
  }, [code]);

  if (!draftApi) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-gray-700 bg-gray-900 text-sm text-gray-500">
        Configure an API to see generated code
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2">
        <h3 className="text-sm font-semibold text-gray-300">
          Generated Deluge Function
        </h3>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded px-3 py-1 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {/* Editor */}
      <div className="flex-1">
        <Editor
          language="deluge"
          theme={DELUGE_THEME}
          value={code}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            fontSize: 13,
            wordWrap: "on",
            domReadOnly: true,
            contextmenu: false,
          }}
        />
      </div>
    </div>
  );
}
