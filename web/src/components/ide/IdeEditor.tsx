import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor, { DiffEditor, type OnMount } from "@monaco-editor/react";
import type { editor as monacoEditor } from "monaco-editor";
import { useDelugeLanguage } from "../../hooks/useMonaco";
import { useMonaco } from "@monaco-editor/react";
import { useIdeStore } from "../../stores/ideStore";
import { useToastStore } from "../../stores/toastStore";
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
  const tabBarRef = useRef<HTMLDivElement>(null);
  const [showTabMenu, setShowTabMenu] = useState(false);
  const [hasOverflow, setHasOverflow] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  const tabs = useIdeStore((s) => s.tabs);
  const activeTabId = useIdeStore((s) => s.activeTabId);
  const diagnostics = useIdeStore((s) => s.diagnostics);
  const appStructure = useIdeStore((s) => s.appStructure);
  const setActiveTab = useIdeStore((s) => s.setActiveTab);
  const closeTab = useIdeStore((s) => s.closeTab);
  const updateTabContent = useIdeStore((s) => s.updateTabContent);
  const setInspectorData = useIdeStore((s) => s.setInspectorData);

  /** Close a tab, prompting to save if dirty. */
  const handleCloseTab = useCallback(
    (tabId: string) => {
      const tab = tabs.find((t) => t.id === tabId);
      if (tab?.isDirty) {
        const choice = window.confirm(
          `"${tab.name}" has unsaved changes.\n\nPress OK to discard, or Cancel to go back.`,
        );
        if (!choice) return;
      }
      closeTab(tabId);
    },
    [tabs, closeTab],
  );

  const activeTab = useMemo(
    () => tabs.find((t) => t.id === activeTabId) ?? null,
    [tabs, activeTabId],
  );

  // Reset diff view when switching tabs
  useEffect(() => {
    setShowDiff(false);
  }, [activeTabId]);

  // --- Detect tab bar overflow ---
  useEffect(() => {
    const el = tabBarRef.current;
    if (!el) return;

    const check = () => {
      setHasOverflow(el.scrollWidth > el.clientWidth + 2);
    };

    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [tabs.length]);

  // Close tab menu when clicking outside
  useEffect(() => {
    if (!showTabMenu) return;
    const handler = () => setShowTabMenu(false);
    window.addEventListener("click", handler);
    return () => window.removeEventListener("click", handler);
  }, [showTabMenu]);

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

      // Ctrl+S / Cmd+S: save the active file
      editor.addAction({
        id: "forgeds-save-file",
        label: "Save File",
        keybindings: [
          // Monaco KeyMod/KeyCode values: CtrlCmd = 2048, KeyS = 49
          2048 | 49,
        ],
        run: () => {
          const { activeTabId: tabId, tabs: currentTabs } = useIdeStore.getState();
          if (!tabId) return;
          const tab = currentTabs.find((t) => t.id === tabId);
          if (!tab?.isDirty) return;

          useIdeStore.getState().saveFile(tabId).then((ok) => {
            if (ok) {
              useToastStore.getState().success("Saved", tab.name);
            }
          });
        },
      });

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
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "#6b7280",
          fontSize: 14,
          fontFamily: "inherit",
          gap: 8,
        }}
      >
        <span>Open a file from the Explorer to start editing</span>
        <span style={{ fontSize: 11, color: "#4b5563" }}>
          Ctrl+P to search files &middot; Ctrl+Shift+F to search content
        </span>
      </div>
    );
  }

  const breadcrumbs = activeTab ? parseBreadcrumbs(activeTab.path) : [];
  const originalContent = activeTab?.originalContent ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* --- Tab bar with overflow handling --- */}
      <div style={{ display: "flex", flexShrink: 0, backgroundColor: "#111118", borderBottom: "1px solid #1e1e2e", position: "relative" }}>
        <div
          ref={tabBarRef}
          style={{
            display: "flex",
            overflowX: "auto",
            flex: 1,
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
                  flexShrink: 0,
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
                    handleCloseTab(tab.id);
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

        {/* Tab overflow dropdown trigger */}
        {hasOverflow && (
          <div style={{ display: "flex", alignItems: "center", borderLeft: "1px solid #1e1e2e", flexShrink: 0 }}>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowTabMenu((v) => !v);
              }}
              style={{
                padding: "6px 8px",
                color: "#9ca3af",
                cursor: "pointer",
                background: "transparent",
                border: "none",
                fontSize: 12,
              }}
              title="Show all tabs"
            >
              &#x2026;
            </button>

            {/* Dropdown menu */}
            {showTabMenu && (
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  zIndex: 30,
                  minWidth: 200,
                  maxHeight: 300,
                  overflowY: "auto",
                  backgroundColor: "#1e1e2e",
                  border: "1px solid #374151",
                  borderRadius: 6,
                  boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                }}
              >
                {tabs.map((tab) => {
                  const isActive = tab.id === activeTabId;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => {
                        setActiveTab(tab.id);
                        setShowTabMenu(false);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        width: "100%",
                        padding: "6px 12px",
                        cursor: "pointer",
                        fontSize: 12,
                        color: isActive ? "#e5e7eb" : "#9ca3af",
                        backgroundColor: isActive ? "#2a2a4a" : "transparent",
                        border: "none",
                        textAlign: "left",
                        whiteSpace: "nowrap",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#262640";
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "transparent";
                      }}
                    >
                      <span style={{ fontSize: 11 }}>{getFileIcon(tab.name)}</span>
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{tab.name}</span>
                      {tab.isDirty && (
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            backgroundColor: "#f59e0b",
                            flexShrink: 0,
                          }}
                        />
                      )}
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCloseTab(tab.id);
                        }}
                        style={{
                          marginLeft: 4,
                          fontSize: 12,
                          color: "#6b7280",
                          cursor: "pointer",
                          padding: "0 2px",
                          borderRadius: 3,
                        }}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLSpanElement).style.color = "#e5e7eb";
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLSpanElement).style.color = "#6b7280";
                        }}
                      >
                        x
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* --- Breadcrumb bar with diff toggle --- */}
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

          {/* Diff toggle — only show for dirty files that have originalContent */}
          {activeTab.isDirty && originalContent && (
            <button
              type="button"
              onClick={() => setShowDiff((v) => !v)}
              style={{
                marginLeft: "auto",
                padding: "1px 6px",
                fontSize: 10,
                fontWeight: 500,
                color: showDiff ? "#818cf8" : "#6b7280",
                backgroundColor: showDiff ? "#1e1b4b" : "transparent",
                border: `1px solid ${showDiff ? "#4338ca" : "#374151"}`,
                borderRadius: 3,
                cursor: "pointer",
              }}
              title="Toggle diff view"
            >
              Diff
            </button>
          )}
        </div>
      )}

      {/* --- Monaco Editor or Diff Editor --- */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {activeTab && showDiff && originalContent ? (
          <DiffEditor
            key={`diff-${activeTab.id}`}
            original={originalContent}
            modified={activeTab.content}
            language={activeTab.language}
            theme={DELUGE_THEME}
            options={{
              readOnly: false,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 14,
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
            onMount={(editor) => {
              // Allow editing in the modified side and sync back
              const modifiedEditor = editor.getModifiedEditor();
              modifiedEditor.onDidChangeModelContent(() => {
                const value = modifiedEditor.getValue();
                if (activeTabId && value !== undefined) {
                  updateTabContent(activeTabId, value);
                }
              });
            }}
          />
        ) : activeTab ? (
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
        ) : null}
      </div>
    </div>
  );
}
