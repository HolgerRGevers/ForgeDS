import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRepoStore } from "../../stores/repoStore";
import { useIdeStore } from "../../stores/ideStore";
import type { GitTreeNode } from "../../types/github";

interface QuickOpenModalProps {
  onClose: () => void;
}

/** Simple fuzzy match: checks if all characters of the pattern appear in order in the target. */
function fuzzyMatch(pattern: string, target: string): { match: boolean; score: number } {
  const p = pattern.toLowerCase();
  const t = target.toLowerCase();

  if (p.length === 0) return { match: true, score: 0 };

  let pi = 0;
  let score = 0;
  let prevMatchIdx = -2;

  for (let ti = 0; ti < t.length && pi < p.length; ti++) {
    if (t[ti] === p[pi]) {
      // Bonus for consecutive matches
      if (ti === prevMatchIdx + 1) score += 5;
      // Bonus for match at start of word (after / or .)
      if (ti === 0 || t[ti - 1] === "/" || t[ti - 1] === "." || t[ti - 1] === "_" || t[ti - 1] === "-") {
        score += 10;
      }
      // Penalty for distance from start
      score += Math.max(0, 5 - ti * 0.1);
      prevMatchIdx = ti;
      pi++;
    }
  }

  return { match: pi === p.length, score };
}

/** Flatten nested GitTreeNode into flat list of file paths. */
function flattenTree(nodes: GitTreeNode[]): string[] {
  const paths: string[] = [];
  const walk = (items: GitTreeNode[]) => {
    for (const n of items) {
      if (n.type === "blob") {
        paths.push(n.path);
      }
      if (n.children) walk(n.children);
    }
  };
  walk(nodes);
  return paths;
}

export function QuickOpenModal({ onClose }: QuickOpenModalProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const repoTree = useRepoStore((s) => s.repoTree);
  const tabs = useIdeStore((s) => s.tabs);
  const fetchFileContent = useRepoStore((s) => s.fetchFileContent);

  // Build the searchable list: open tab paths + repo tree paths (deduplicated)
  const allPaths = useMemo(() => {
    const tabPaths = tabs.map((t) => t.path);
    const treePaths = flattenTree(repoTree);
    const seen = new Set(tabPaths);
    const combined = [...tabPaths];
    for (const p of treePaths) {
      if (!seen.has(p)) {
        seen.add(p);
        combined.push(p);
      }
    }
    return combined;
  }, [tabs, repoTree]);

  // Filter and rank by fuzzy match
  const filtered = useMemo(() => {
    if (!query.trim()) {
      // Show recently open tabs first, then repo files (limit 50)
      return allPaths.slice(0, 50).map((path) => ({ path, score: 0 }));
    }
    const matches: Array<{ path: string; score: number }> = [];
    for (const path of allPaths) {
      // Match against filename primarily, then full path
      const name = path.split("/").pop() ?? path;
      const nameResult = fuzzyMatch(query, name);
      const pathResult = fuzzyMatch(query, path);
      const bestScore = Math.max(
        nameResult.match ? nameResult.score + 20 : 0, // filename matches get bonus
        pathResult.match ? pathResult.score : 0,
      );
      if (nameResult.match || pathResult.match) {
        matches.push({ path, score: bestScore });
      }
    }
    matches.sort((a, b) => b.score - a.score);
    return matches.slice(0, 50);
  }, [query, allPaths]);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [filtered]);

  // Focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Scroll selected item into view
  useEffect(() => {
    const item = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const openFile = useCallback(
    async (path: string) => {
      const { openTab, setActiveTab, tabs: currentTabs } = useIdeStore.getState();
      const existing = currentTabs.find((t) => t.path === path || t.id === path);
      if (existing) {
        setActiveTab(existing.id);
        onClose();
        return;
      }

      const name = path.split("/").pop() ?? path;
      const ext = name.split(".").pop() ?? "";
      const langMap: Record<string, string> = {
        dg: "deluge", ds: "plaintext", py: "python", json: "json",
        yaml: "yaml", yml: "yaml", md: "markdown", sql: "sql",
        js: "javascript", ts: "typescript", tsx: "typescript",
        jsx: "javascript", html: "html", css: "css",
      };

      // Try to fetch content from repo
      let content = "";
      try {
        content = await fetchFileContent(path);
      } catch {
        // Content will be loaded by IdePage's read_file effect
      }

      openTab({
        id: path,
        name,
        path,
        content,
        language: langMap[ext] ?? "plaintext",
        isDirty: false,
      });
      onClose();
    },
    [onClose, fetchFileContent],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (filtered[selectedIndex]) {
            openFile(filtered[selectedIndex].path);
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
      }
    },
    [filtered, selectedIndex, openFile, onClose],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-[500px] max-w-[90vw] overflow-hidden rounded-lg border border-gray-600 bg-gray-800 shadow-2xl">
        {/* Search input */}
        <div className="border-b border-gray-700 px-3 py-2">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type to search files..."
            className="w-full bg-transparent text-sm text-gray-200 placeholder-gray-500 outline-none"
          />
        </div>

        {/* Results list */}
        <div ref={listRef} className="max-h-[300px] overflow-y-auto">
          {filtered.length === 0 && query && (
            <div className="px-3 py-4 text-center text-sm text-gray-500">
              No matching files
            </div>
          )}
          {filtered.map((item, i) => {
            const name = item.path.split("/").pop() ?? item.path;
            const dir = item.path.includes("/")
              ? item.path.slice(0, item.path.lastIndexOf("/"))
              : "";
            const isOpen = tabs.some((t) => t.path === item.path);
            return (
              <button
                key={item.path}
                type="button"
                onClick={() => openFile(item.path)}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm ${
                  i === selectedIndex
                    ? "bg-blue-600/40 text-white"
                    : "text-gray-300 hover:bg-gray-700/50"
                }`}
              >
                <span className="shrink-0 text-xs">
                  {getQuickIcon(name)}
                </span>
                <span className="truncate font-medium">{name}</span>
                {dir && (
                  <span className="truncate text-xs text-gray-500">{dir}</span>
                )}
                {isOpen && (
                  <span className="ml-auto shrink-0 rounded bg-gray-700 px-1 py-0.5 text-[9px] text-gray-400">
                    open
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-700 px-3 py-1.5 text-[10px] text-gray-500">
          <span>{filtered.length} file{filtered.length !== 1 ? "s" : ""}</span>
          <span>
            <kbd className="rounded border border-gray-600 px-1">↑↓</kbd> navigate{" "}
            <kbd className="rounded border border-gray-600 px-1">↵</kbd> open{" "}
            <kbd className="rounded border border-gray-600 px-1">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}

function getQuickIcon(name: string): string {
  if (name.endsWith(".dg")) return "\u26A1";
  if (name.endsWith(".ds")) return "\u{1F4E6}";
  if (name.endsWith(".json")) return "{}";
  if (name.endsWith(".yaml") || name.endsWith(".yml")) return "\u2699";
  if (name.endsWith(".py")) return "\u{1F40D}";
  if (name.endsWith(".md")) return "\u{1F4DD}";
  if (name.endsWith(".sql")) return "\u{1F5C4}";
  return "\u{1F4C4}";
}
