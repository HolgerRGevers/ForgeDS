import { useCallback, useEffect, useMemo, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor as monacoEditor } from "monaco-editor";
import { useDelugeLanguage } from "../../hooks/useMonaco";
import { useMonaco } from "@monaco-editor/react";
import { useIdeStore } from "../../stores/ideStore";
import { DELUGE_THEME } from "../../lib/deluge-language";
import type { LintDiagnostic, InspectorData } from "../../types/ide";

// --- File extension icons ---

const extIcons: Record<string, string> = {
  ".dg": "\u26A1",
  ".ds": "\u{1F4E6}",
  ".json": "{}",
  ".yaml": "\u2699",
  ".yml": "\u2699",
  ".md": "\u{1F4DD}",
  ".sql": "\u{1F5C4}",
  ".py": "\u{1F40D}",
};

function getFileIcon(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot === -1) return "\u{1F4C4}";
  const ext = filename.substring(dot).toLowerCase();
  return extIcons[ext] ?? "\u{1F4C4}";
}

// --- Breadcrumb parsing ---

/**
 * Parse a file path into breadcrumb segments.
 * e.g. "src/deluge/form-workflows/expense_claim.on_validate.dg"
 *   -> ["Expense Claim", "on_validate"]
 */
function parseBreadcrumbs(path: string): string[] {
  const segments = path.replace(/\\/g, "/").split("/");
  const filename = segments[segments.length - 1] ?? "";

  // Remove extension
  const base = filename.replace(/\.\w+$/, "");

  // Split on dots: "expense_claim.on_validate" -> ["expense_claim", "on_validate"]
  const parts = base.split(".");

  return parts.map((part) =>
    part
      .split(/[_-]/)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" "),
  );
}

// --- Severity mapping ---

function toMarkerSeverity(
  monaco: typeof import("monaco-editor"),
  severity: LintDiagnostic["severity"],
): number {
  switch (severity) {
    case "error":
      return monaco.MarkerSeverity.Error;
    case "warning":
      return monaco.MarkerSeverity.Warning;
    case "info":
      return monaco.MarkerSeverity.Info;
  }
}

// --- Component ---

export function IdeEditor() {
  useDelugeLanguage();
  const monaco = useMonaco();
  const editorRef = useRef<monacoEditor.IStandaloneCodeEditor | null>(null);

  const tabs = useIdeStore((s) => s.tabs);
  const activeTabId = useIdeStore((s) => s.activeTabId);
  const diagnostics = useIdeStore((s) => s.diagnostics);
  const appStructure = useIdeStore((s) => s.appStructure);
  const setActiveTab = useIdeStore((s) => s.setActiveTab);
  const closeTab = useIdeStore((s) => s.closeTab);
  const updateTabContent = useIdeStore((s) => s.updateTabContent);
  const setInspectorData = useIdeStore((s) => s.setInspectorData);

  const activeTab = useMemo(
    () => tabs.find((t) => t.id === activeTabId) ?? null,
    [tabs, activeTabId],
  );

  // --- Set Monaco markers when diagnostics or active tab change ---

  useEffect(() => {
    if (!monaco || !activeTab) return;

    const model = editorRef.current?.getModel();
    if (!model) return;

    const fileDiagnostics = diagnostics.filter(
      (d) => d.file === activeTab.path,
    );

    const markers = fileDiagnostics.map((d) => ({
      severity: toMarkerSeverity(monaco, d.severity),
      message: `${d.message} [${d.rule}]`,
      startLineNumber: d.line,
      startColumn: 1,
      endLineNumber: d.line,
      endColumn: model.getLineMaxColumn(d.line),
    }));

    monaco.editor.setModelMarkers(model, "deluge-lint", markers);
  }, [monaco, diagnostics, activeTab]);

  // --- Editor mount handler ---

  const handleEditorMount: OnMount = useCallback(
    (editor) => {
      editorRef.current = editor;

      // Click-to-inspect: on cursor position change, look up the word
      editor.onDidChangeCursorPosition((e) => {
        const model = editor.getModel();
        if (!model) return;

        const word = model.getWordAtPosition(e.position);
        if (!word) return;

        const identifier = word.word;

        // Look up in the node index — search by label (case-insensitive)
        // since cursor words are field names like "Amount_ZAR", not node IDs like "field-amount"
        if (appStructure?.nodeIndex) {
          let node: import("../../types/ide").TreeNode | undefined;
          const lowerIdentifier = identifier.toLowerCase();
          for (const candidate of appStructure.nodeIndex.values()) {
            if (candidate.label.toLowerCase() === lowerIdentifier) {
              node = candidate;
              break;
            }
          }
          if (node) {
            const data: InspectorData = {
              type:
                node.type === "field"
                  ? "field"
                  : node.type === "form"
                    ? "form"
                    : "variable",
              name: node.label,
              properties: [
                { label: "Type", value: node.type },
                ...(node.fieldType
                  ? [{ label: "Field Type", value: node.fieldType }]
                  : []),
                ...(node.trigger
                  ? [{ label: "Trigger", value: node.trigger }]
                  : []),
              ],
              relationships: [],
              usages: [],
            };
            setInspectorData(data);
          }
        }
      });
    },
    [appStructure, setInspectorData],
  );

  // --- onChange ---

  const handleContentChange = useCallback(
    (value: string | undefined) => {
      if (activeTabId && value !== undefined) {
        updateTabContent(activeTabId, value);
      }
    },
    [activeTabId, updateTabContent],
  );

  // --- Empty state ---

  if (tabs.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "#6b7280",
          fontSize: 14,
          fontFamily: "inherit",
        }}
      >
        Open a file from the Explorer to start editing
      </div>
    );
  }

  const breadcrumbs = activeTab ? parseBreadcrumbs(activeTab.path) : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* --- Tab bar --- */}
      <div
        style={{
          display: "flex",
          overflowX: "auto",
          flexShrink: 0,
          backgroundColor: "#111118",
          borderBottom: "1px solid #1e1e2e",
          scrollbarWidth: "thin",
        }}
      >
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          return (
            <div
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                cursor: "pointer",
                whiteSpace: "nowrap",
                fontSize: 13,
                color: isActive ? "#e5e7eb" : "#9ca3af",
                backgroundColor: isActive ? "#1a1a2e" : "transparent",
                borderBottom: isActive ? "2px solid #6366f1" : "2px solid transparent",
                userSelect: "none",
              }}
            >
              <span style={{ fontSize: 12 }}>{getFileIcon(tab.name)}</span>
              <span>{tab.name}</span>
              {tab.isDirty && (
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: "#f59e0b",
                    flexShrink: 0,
                  }}
                />
              )}
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(tab.id);
                }}
                style={{
                  marginLeft: 4,
                  fontSize: 14,
                  lineHeight: 1,
                  color: "#6b7280",
                  cursor: "pointer",
                  borderRadius: 3,
                  padding: "0 2px",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLSpanElement).style.color = "#e5e7eb";
                  (e.currentTarget as HTMLSpanElement).style.backgroundColor = "#374151";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLSpanElement).style.color = "#6b7280";
                  (e.currentTarget as HTMLSpanElement).style.backgroundColor = "transparent";
                }}
              >
                x
              </span>
            </div>
          );
        })}
      </div>

      {/* --- Breadcrumb bar --- */}
      {activeTab && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 12px",
            fontSize: 12,
            color: "#6b7280",
            backgroundColor: "#0f0f17",
            borderBottom: "1px solid #1e1e2e",
            flexShrink: 0,
          }}
        >
          {breadcrumbs.map((seg, i) => (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {i > 0 && <span style={{ color: "#4b5563" }}>&gt;</span>}
              <span style={{ cursor: "pointer" }}>{seg}</span>
            </span>
          ))}
        </div>
      )}

      {/* --- Monaco Editor --- */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {activeTab && (
          <Editor
            key={activeTab.id}
            language={activeTab.language}
            value={activeTab.content}
            theme={DELUGE_THEME}
            onChange={handleContentChange}
            onMount={handleEditorMount}
            options={{
              minimap: { enabled: true, maxColumn: 80 },
              lineNumbers: "on",
              wordWrap: "off",
              fontSize: 14,
              tabSize: 4,
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
          />
        )}
      </div>
    </div>
  );
}
