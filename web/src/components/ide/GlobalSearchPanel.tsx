import { useCallback, useEffect, useRef, useState } from "react";
import { useBridgeStore } from "../../stores/bridgeStore";
import { useIdeStore } from "../../stores/ideStore";

interface SearchResult {
  file: string;
  line: number;
  col: number;
  text: string;
}

interface GlobalSearchPanelProps {
  onClose: () => void;
}

export function GlobalSearchPanel({ onClose }: GlobalSearchPanelProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [useRegex, setUseRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [searchScope, setSearchScope] = useState<"project" | "open">("project");
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const send = useBridgeStore((s) => s.send);
  const tabs = useIdeStore((s) => s.tabs);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Search across open tabs (client-side)
  const searchOpenTabs = useCallback(
    (q: string): SearchResult[] => {
      if (!q) return [];
      const flags = caseSensitive ? "" : "i";
      let pattern: RegExp;
      try {
        pattern = useRegex ? new RegExp(q, flags) : new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), flags);
      } catch {
        return [];
      }

      const matches: SearchResult[] = [];
      for (const tab of tabs) {
        if (!tab.content) continue;
        const lines = tab.content.split("\n");
        for (let i = 0; i < lines.length; i++) {
          const m = pattern.exec(lines[i]);
          if (m) {
            matches.push({
              file: tab.path,
              line: i + 1,
              col: m.index,
              text: lines[i].slice(0, 300),
            });
            if (matches.length >= 200) return matches;
          }
        }
      }
      return matches;
    },
    [tabs, useRegex, caseSensitive],
  );

  // Perform search (debounced)
  const doSearch = useCallback(
    (q: string) => {
      if (!q.trim()) {
        setResults([]);
        setTruncated(false);
        return;
      }

      if (searchScope === "open" || bridgeStatus !== "connected") {
        const matches = searchOpenTabs(q);
        setResults(matches);
        setTruncated(matches.length >= 200);
        return;
      }

      // Bridge search
      setSearching(true);
      send("search_files", {
        query: q,
        regex: useRegex,
        case_sensitive: caseSensitive,
      })
        .then((resp) => {
          const data = resp as unknown as { results: SearchResult[]; truncated: boolean };
          setResults(data.results ?? []);
          setTruncated(data.truncated ?? false);
        })
        .catch(() => {
          // Fallback to open tabs search
          const matches = searchOpenTabs(q);
          setResults(matches);
          setTruncated(false);
        })
        .finally(() => setSearching(false));
    },
    [searchScope, bridgeStatus, send, useRegex, caseSensitive, searchOpenTabs],
  );

  // Debounce input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, doSearch]);

  const handleResultClick = useCallback(
    (result: SearchResult) => {
      const { openTab, setActiveTab, tabs: currentTabs } = useIdeStore.getState();
      const existing = currentTabs.find((t) => t.path === result.file);
      if (existing) {
        setActiveTab(existing.id);
      } else {
        const name = result.file.split("/").pop() ?? result.file;
        const ext = name.split(".").pop() ?? "";
        const langMap: Record<string, string> = {
          dg: "deluge", ds: "plaintext", py: "python", json: "json",
          yaml: "yaml", yml: "yaml", md: "markdown", sql: "sql",
        };
        openTab({
          id: result.file,
          name,
          path: result.file,
          content: "",
          language: langMap[ext] ?? "plaintext",
          isDirty: false,
        });
      }
    },
    [],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [onClose],
  );

  // Group results by file
  const grouped = new Map<string, SearchResult[]>();
  for (const r of results) {
    const list = grouped.get(r.file) ?? [];
    list.push(r);
    grouped.set(r.file, list);
  }

  return (
    <div className="flex h-full flex-col" onKeyDown={handleKeyDown}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-2 py-1.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Search
        </span>
        <button
          onClick={onClose}
          className="rounded px-1.5 py-0.5 text-xs text-gray-500 hover:bg-gray-700 hover:text-gray-300"
        >
          ✕
        </button>
      </div>

      {/* Search input */}
      <div className="space-y-1 border-b border-gray-700 px-2 py-2">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search files..."
          className="w-full rounded bg-gray-800 px-2 py-1.5 text-xs text-gray-200 placeholder-gray-600 outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-[10px] text-gray-500">
            <input
              type="checkbox"
              checked={useRegex}
              onChange={(e) => setUseRegex(e.target.checked)}
              className="h-3 w-3 rounded border-gray-600 bg-gray-800"
            />
            Regex
          </label>
          <label className="flex items-center gap-1 text-[10px] text-gray-500">
            <input
              type="checkbox"
              checked={caseSensitive}
              onChange={(e) => setCaseSensitive(e.target.checked)}
              className="h-3 w-3 rounded border-gray-600 bg-gray-800"
            />
            Aa
          </label>
          <div className="ml-auto inline-flex rounded border border-gray-700 bg-gray-800 p-0.5">
            <button
              type="button"
              onClick={() => setSearchScope("project")}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                searchScope === "project"
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Project
            </button>
            <button
              type="button"
              onClick={() => setSearchScope("open")}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                searchScope === "open"
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Open Files
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {searching && (
          <div className="flex items-center justify-center py-6 text-xs text-gray-500">
            Searching...
          </div>
        )}

        {!searching && query && results.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-gray-500">
            No results found
          </div>
        )}

        {!searching && !query && (
          <div className="px-3 py-6 text-center text-xs text-gray-500">
            <p>Type to search across {searchScope === "project" ? "project files" : "open tabs"}</p>
            {bridgeStatus !== "connected" && searchScope === "project" && (
              <p className="mt-1 text-gray-600">Bridge offline — searching open tabs only</p>
            )}
          </div>
        )}

        {!searching &&
          Array.from(grouped.entries()).map(([file, matches]) => (
            <div key={file} className="border-b border-gray-700/30">
              <div className="sticky top-0 bg-gray-800/90 px-3 py-1 text-[11px] font-medium text-gray-400">
                {file}
                <span className="ml-1 text-gray-600">({matches.length})</span>
              </div>
              {matches.map((r, i) => (
                <button
                  key={`${r.file}:${r.line}:${i}`}
                  type="button"
                  onClick={() => handleResultClick(r)}
                  className="flex w-full items-baseline gap-2 px-3 py-1 text-left text-xs hover:bg-gray-700/40"
                >
                  <span className="shrink-0 font-mono text-[10px] text-gray-600">
                    {r.line}
                  </span>
                  <span className="truncate text-gray-300">
                    <HighlightedLine text={r.text} query={query} useRegex={useRegex} caseSensitive={caseSensitive} />
                  </span>
                </button>
              ))}
            </div>
          ))}

        {truncated && (
          <div className="px-3 py-2 text-center text-[10px] text-yellow-500">
            Results truncated — refine your search
          </div>
        )}
      </div>
    </div>
  );
}

/** Highlight matching portions of a line. */
function HighlightedLine({
  text,
  query,
  useRegex,
  caseSensitive,
}: {
  text: string;
  query: string;
  useRegex: boolean;
  caseSensitive: boolean;
}) {
  if (!query) return <>{text}</>;

  const flags = caseSensitive ? "g" : "gi";
  let pattern: RegExp;
  try {
    pattern = useRegex ? new RegExp(query, flags) : new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), flags);
  } catch {
    return <>{text}</>;
  }

  const parts: Array<{ text: string; match: boolean }> = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, m.index), match: false });
    }
    parts.push({ text: m[0], match: true });
    lastIndex = pattern.lastIndex;
    if (m[0].length === 0) break; // prevent infinite loop on zero-length match
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), match: false });
  }

  return (
    <>
      {parts.map((p, i) =>
        p.match ? (
          <span key={i} className="rounded bg-yellow-500/30 text-yellow-200">
            {p.text}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}
