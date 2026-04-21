import { useCallback, useEffect, useRef, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import type { ConsoleEntry, ConsoleTab, LintDiagnostic, RelationshipLink } from "../../types/ide";

// --- Severity helpers ---

const severityOrder: Record<string, number> = { error: 0, warning: 1, info: 2 };

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case "error":
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
          !
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center text-yellow-400">
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
            <path d="M8 1L1 14h14L8 1zm0 4v5m0 2v1" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
        </span>
      );
    default:
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
          i
        </span>
      );
  }
}

// --- Bridge required message ---

function BridgeRequiredMessage({ feature }: { feature: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 text-sm text-gray-500">
      <span>{feature} requires the bridge server</span>
      <span className="font-mono text-xs text-gray-600">python -m bridge</span>
    </div>
  );
}

// --- Tab definitions ---

const TAB_LABELS: Record<ConsoleTab, string> = {
  lint: "Lint",
  build: "Build",
  relationships: "Relationships",
  ai: "AI Chat",
};

const TABS: ConsoleTab[] = ["lint", "build", "relationships", "ai"];

// --- Lint Tab ---

interface LintTabProps {
  diagnostics: LintDiagnostic[];
  onFileClick?: (file: string, line: number) => void;
}

function LintTab({ diagnostics, onFileClick }: LintTabProps) {
  const sorted = [...diagnostics].sort(
    (a, b) => (severityOrder[a.severity] ?? 2) - (severityOrder[b.severity] ?? 2),
  );

  const errorCount = diagnostics.filter((d) => d.severity === "error").length;
  const warnCount = diagnostics.filter((d) => d.severity === "warning").length;
  const infoCount = diagnostics.filter((d) => d.severity === "info").length;

  return (
    <div className="flex h-full flex-col">
      {/* Summary bar */}
      <div className="flex items-center gap-3 border-b border-gray-700/50 px-3 py-1.5 text-xs text-gray-400">
        <span className="text-red-400">{errorCount} errors</span>
        <span className="text-yellow-400">{warnCount} warnings</span>
        <span className="text-blue-400">{infoCount} info</span>
      </div>

      {/* Diagnostics list */}
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            No diagnostics
          </div>
        ) : (
          sorted.map((d, i) => (
            <div
              key={`${d.file}:${d.line}:${d.rule}:${i}`}
              className="flex items-start gap-2 border-b border-gray-700/30 px-3 py-1.5 text-sm leading-tight hover:bg-gray-700/30"
            >
              <SeverityIcon severity={d.severity} />
              <span className="flex-shrink-0 font-mono text-xs text-gray-500">
                {d.rule}
              </span>
              <span className="flex-1 truncate text-gray-300">{d.message}</span>
              <button
                onClick={() => onFileClick?.(d.file, d.line)}
                className="flex-shrink-0 font-mono text-xs text-indigo-400 hover:text-indigo-300 hover:underline"
              >
                {d.file}:{d.line}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// --- Build Tab ---

interface BuildTabProps {
  entries: ConsoleEntry[];
}

function BuildTab({ entries }: BuildTabProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const filtered = entries.filter(
    (e) => e.type === "build" || e.type === "info" || e.type === "error",
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered.length]);

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto p-2 font-mono text-xs leading-5">
      {filtered.length === 0 ? (
        <div className="flex h-full items-center justify-center text-sm text-gray-500">
          No build output
        </div>
      ) : (
        filtered.map((entry) => (
          <div
            key={entry.id}
            className={`${
              entry.type === "error" ? "text-red-400" : "text-gray-300"
            }`}
          >
            <span className="mr-2 text-gray-600">
              {new Date(entry.timestamp).toLocaleTimeString()}
            </span>
            {entry.message}
          </div>
        ))
      )}
    </div>
  );
}

// --- Relationships Tab ---

interface RelationshipsTabProps {
  relationships: RelationshipLink[];
  elementName: string | null;
}

function RelationshipsTab({ relationships, elementName }: RelationshipsTabProps) {
  if (!elementName) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Select an element to view relationships
      </div>
    );
  }

  // Group by relationship type
  const grouped = new Map<string, RelationshipLink[]>();
  for (const rel of relationships) {
    const group = grouped.get(rel.relationship) ?? [];
    group.push(rel);
    grouped.set(rel.relationship, group);
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-gray-700/50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
        Element Relationships
      </div>
      {relationships.length === 0 ? (
        <div className="px-3 py-4 text-sm text-gray-500">
          No relationships found for "{elementName}"
        </div>
      ) : (
        Array.from(grouped.entries()).map(([relType, links]) => (
          <div key={relType} className="border-b border-gray-700/30 px-3 py-2">
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
              {relType}
            </h4>
            {links.map((link) => (
              <div
                key={`${link.relationship}-${link.targetId}`}
                className="flex items-center gap-2 py-0.5 text-sm"
              >
                <span className="text-gray-300">{elementName}</span>
                <span className="text-gray-500">{link.relationship}</span>
                <span className="text-indigo-400">{link.targetLabel}</span>
                <span className="rounded bg-gray-700 px-1 py-0.5 text-[10px] uppercase text-gray-400">
                  {link.targetType}
                </span>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}

// --- AI Chat Tab ---

interface ChatMessage {
  id: number;
  role: "user" | "ai";
  text: string;
}

interface AiChatTabProps {
  bridgeStatus: string;
  onSend: (message: string) => Promise<string>;
}

function AiChatTab({ bridgeStatus, onSend }: AiChatTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const msgIdRef = useRef(0);

  const isConnected = bridgeStatus === "connected";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !isConnected) return;

    const userMsg: ChatMessage = { id: ++msgIdRef.current, role: "user", text };
    const aiMsgId = ++msgIdRef.current;
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: "ai",
      text: "Thinking...",
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInput("");

    try {
      const responseText = await onSend(text);
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, text: responseText } : m)),
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId ? { ...m, text: "Error: failed to get response." } : m,
        ),
      );
    }
  }, [input, isConnected, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  if (!isConnected) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Connect bridge to use AI Chat
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-2">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Start a conversation
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-200"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="flex items-center gap-2 border-t border-gray-700 px-2 py-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask something..."
          className="flex-1 rounded bg-gray-700 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600"
        >
          Send
        </button>
      </div>
    </div>
  );
}

// --- Main DevConsole ---

export function DevConsole() {
  const [collapsed, setCollapsed] = useState(false);

  const activeConsoleTab = useIdeStore((s) => s.activeConsoleTab);
  const consoleEntries = useIdeStore((s) => s.consoleEntries);
  const diagnostics = useIdeStore((s) => s.diagnostics);
  const inspectorData = useIdeStore((s) => s.inspectorData);
  const setActiveConsoleTab = useIdeStore((s) => s.setActiveConsoleTab);
  const clearConsole = useIdeStore((s) => s.clearConsole);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const bridgeSend = useBridgeStore((s) => s.send);

  const handleFileClick = useCallback((_file: string, _line: number) => {
    // Future: open file in editor at the given line
  }, []);

  const handleAiSend = useCallback(
    async (message: string): Promise<string> => {
      const result = await bridgeSend("ai_chat", { message });
      const data = result as unknown as { response: string };
      return data.response ?? "No response received.";
    },
    [bridgeSend],
  );

  return (
    <div className="flex flex-col border-t border-gray-700 bg-gray-800">
      {/* Header: drag handle area + tab bar + actions */}
      <div className="flex items-center border-b border-gray-700">
        {/* Toggle / drag handle */}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center text-gray-400 hover:text-gray-200"
          title={collapsed ? "Expand console" : "Collapse console"}
        >
          <svg
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={`h-3 w-3 transition-transform ${collapsed ? "rotate-180" : ""}`}
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </button>

        {/* Tab bar */}
        <div className="flex flex-1 items-center gap-0 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveConsoleTab(tab);
                if (collapsed) setCollapsed(false);
              }}
              className={`border-b-2 px-3 py-1.5 text-xs font-medium transition-colors ${
                activeConsoleTab === tab
                  ? "border-indigo-400 text-indigo-300"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        {/* Clear button */}
        <button
          onClick={clearConsole}
          className="mr-1 rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-700 hover:text-gray-300"
          title="Clear console"
        >
          Clear
        </button>
      </div>

      {/* Tab content */}
      {!collapsed && (
        <div className="h-48 min-h-0">
          {activeConsoleTab === "lint" && (
            bridgeStatus !== "connected"
              ? <BridgeRequiredMessage feature="Lint" />
              : <LintTab diagnostics={diagnostics} onFileClick={handleFileClick} />
          )}
          {activeConsoleTab === "build" && (
            <BuildTab entries={consoleEntries} />
          )}
          {activeConsoleTab === "relationships" && (
            bridgeStatus !== "connected"
              ? <BridgeRequiredMessage feature="Relationships" />
              : <RelationshipsTab
                  relationships={inspectorData?.relationships ?? []}
                  elementName={inspectorData?.name ?? null}
                />
          )}
          {activeConsoleTab === "ai" && (
            <AiChatTab bridgeStatus={bridgeStatus} onSend={handleAiSend} />
          )}
        </div>
      )}
    </div>
  );
}
