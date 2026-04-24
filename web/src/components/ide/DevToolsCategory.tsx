import { useCallback, useEffect, useRef, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import type {
  ConsoleEntry,
  LintDiagnostic,
  RelationshipLink,
} from "../../types/ide";

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

function BridgeRequiredMessage({ feature }: { feature: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 text-sm text-gray-500">
      <span>{feature} requires the bridge server</span>
      <span className="font-mono text-xs text-gray-600">python -m bridge</span>
    </div>
  );
}

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
      <div className="flex items-center gap-3 border-b border-gray-700/50 px-3 py-1.5 text-xs text-gray-400">
        <span className="text-red-400">{errorCount} errors</span>
        <span className="text-yellow-400">{warnCount} warnings</span>
        <span className="text-blue-400">{infoCount} info</span>
      </div>
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
              <span className="flex-shrink-0 font-mono text-xs text-gray-500">{d.rule}</span>
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

function BuildTab({ entries }: { entries: ConsoleEntry[] }) {
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
          <div key={entry.id} className={entry.type === "error" ? "text-red-400" : "text-gray-300"}>
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

function RelationshipsTab({
  relationships,
  elementName,
}: {
  relationships: RelationshipLink[];
  elementName: string | null;
}) {
  if (!elementName) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Select an element to view relationships
      </div>
    );
  }

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
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">{relType}</h4>
            {links.map((link) => (
              <div key={`${link.relationship}-${link.targetId}`} className="flex items-center gap-2 py-0.5 text-sm">
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

function AiChatTab({
  bridgeStatus,
  onSend,
}: {
  bridgeStatus: string;
  onSend: (message: string) => Promise<string>;
}) {
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
    const aiMsg: ChatMessage = { id: aiMsgId, role: "ai", text: "Thinking..." };
    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInput("");
    try {
      const responseText = await onSend(text);
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, text: responseText } : m)),
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, text: "Error: failed to get response." } : m)),
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
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-2">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Start a conversation
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-200"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
      </div>
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

// --- Main DevToolsCategory ---

export function DevToolsCategory() {
  const activeDevToolsTab = useIdeStore((s) => s.activeDevToolsTab);
  const consoleEntries = useIdeStore((s) => s.consoleEntries);
  const diagnostics = useIdeStore((s) => s.diagnostics);
  const inspectorData = useIdeStore((s) => s.inspectorData);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const bridgeSend = useBridgeStore((s) => s.send);

  const handleFileClick = useCallback((_file: string, _line: number) => {
    // Polish Pass spec will wire this to open the file in the editor at the given line.
  }, []);

  const handleAiSend = useCallback(
    async (message: string): Promise<string> => {
      const result = await bridgeSend("ai_chat", { message });
      const data = result as unknown as { response: string };
      return data.response ?? "No response received.";
    },
    [bridgeSend],
  );

  switch (activeDevToolsTab) {
    case "lint":
      return bridgeStatus !== "connected" ? (
        <BridgeRequiredMessage feature="Lint" />
      ) : (
        <LintTab diagnostics={diagnostics} onFileClick={handleFileClick} />
      );
    case "build":
      return <BuildTab entries={consoleEntries} />;
    case "relationships":
      return bridgeStatus !== "connected" ? (
        <BridgeRequiredMessage feature="Relationships" />
      ) : (
        <RelationshipsTab
          relationships={inspectorData?.relationships ?? []}
          elementName={inspectorData?.name ?? null}
        />
      );
    case "ai":
      return <AiChatTab bridgeStatus={bridgeStatus} onSend={handleAiSend} />;
  }
}
