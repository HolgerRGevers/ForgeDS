import { useCallback, useMemo } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { TreeNode } from "../../types/ide";

// --- Node type icons ---

const nodeIcons: Record<TreeNode["type"], string> = {
  application: "\u{1F4C1}",
  form: "\u{1F4C4}",
  field: "\u25CF",
  workflow: "\u26A1",
  report: "\u{1F4CA}",
  page: "\u{1F5D4}",
  schedule: "\u{1F553}",
  api: "\u2601",
  section: "\u25B8",
};

// --- Filtering logic ---

/** Returns true if `node` or any descendant matches `filter` (case-insensitive). */
function nodeMatchesFilter(node: TreeNode, filter: string): boolean {
  const lowerFilter = filter.toLowerCase();
  if (node.label.toLowerCase().includes(lowerFilter)) return true;
  if (node.children) {
    return node.children.some((child) => nodeMatchesFilter(child, lowerFilter));
  }
  return false;
}

/** Filter a tree, keeping nodes that match or have matching descendants. */
function filterTree(nodes: TreeNode[], filter: string): TreeNode[] {
  if (!filter) return nodes;
  return nodes
    .filter((node) => nodeMatchesFilter(node, filter))
    .map((node) => {
      if (!node.children) return node;
      const filteredChildren = filterTree(node.children, filter);
      return { ...node, children: filteredChildren };
    });
}

// --- TreeNodeItem sub-component ---

interface TreeNodeItemProps {
  node: TreeNode;
  depth: number;
  filter: string;
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
  onToggle: (nodeId: string) => void;
}

function TreeNodeItem({
  node,
  depth,
  filter,
  selectedNodeId,
  onSelect,
  onToggle,
}: TreeNodeItemProps) {
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = node.id === selectedNodeId;
  // When filtering, auto-expand parent nodes that contain matches
  const isExpanded = filter ? true : node.isExpanded ?? false;

  const handleClick = useCallback(() => {
    if (hasChildren) {
      onToggle(node.id);
    }
    onSelect(node.id);
  }, [hasChildren, node.id, onSelect, onToggle]);

  const handleChevronClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onToggle(node.id);
    },
    [node.id, onToggle],
  );

  const icon = nodeIcons[node.type] ?? "\u25CB";

  return (
    <div>
      {/* Node row */}
      <div
        className={`group flex cursor-pointer items-center py-0.5 pr-2 leading-tight hover:bg-gray-800 ${
          isSelected
            ? "border-l-2 border-indigo-400 bg-gray-800/80"
            : "border-l-2 border-transparent"
        }`}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        onClick={handleClick}
        role="treeitem"
        aria-expanded={hasChildren ? isExpanded : undefined}
        aria-selected={isSelected}
      >
        {/* Chevron */}
        <span
          className="inline-flex w-4 flex-shrink-0 items-center justify-center text-gray-500"
          onClick={hasChildren ? handleChevronClick : undefined}
        >
          {hasChildren ? (
            <svg
              className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
              viewBox="0 0 12 12"
              fill="currentColor"
            >
              <path d="M4 2l4 4-4 4z" />
            </svg>
          ) : null}
        </span>

        {/* Icon */}
        <span className="mr-1.5 flex-shrink-0 text-xs">{icon}</span>

        {/* Label */}
        <span
          className={`truncate text-sm ${
            node.type === "field" || node.type === "workflow" || node.type === "api"
              ? "font-mono"
              : ""
          } ${isSelected ? "text-gray-100" : "text-gray-300"}`}
          title={node.label}
        >
          {node.label}
        </span>

        {/* Field type badge */}
        {node.fieldType && (
          <span className="ml-auto flex-shrink-0 text-xs text-gray-500">
            {node.fieldType}
          </span>
        )}

        {/* Trigger badge */}
        {node.trigger && (
          <span className="ml-auto flex-shrink-0 text-xs text-gray-500">
            {node.trigger}
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div role="group">
          {node.children!.map((child) => (
            <TreeNodeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              filter={filter}
              selectedNodeId={selectedNodeId}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- Main component ---

export function AppTreeExplorer() {
  const appStructure = useIdeStore((s) => s.appStructure);
  const selectedNodeId = useIdeStore((s) => s.selectedNodeId);
  const treeFilter = useIdeStore((s) => s.treeFilter);
  const selectNode = useIdeStore((s) => s.selectNode);
  const toggleNode = useIdeStore((s) => s.toggleNode);
  const setTreeFilter = useIdeStore((s) => s.setTreeFilter);

  const handleCollapseAll = useCallback(() => {
    if (!appStructure) return;
    // Collapse every node by toggling any expanded ones
    for (const [, node] of appStructure.nodeIndex) {
      if (node.isExpanded) {
        node.isExpanded = false;
      }
    }
    // Trigger re-render
    useIdeStore.setState({ appStructure: { ...appStructure } });
  }, [appStructure]);

  const filteredTree = useMemo(() => {
    if (!appStructure) return [];
    return filterTree(appStructure.tree, treeFilter);
  }, [appStructure, treeFilter]);

  const noResults = treeFilter && filteredTree.length === 0;

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Explorer
        </span>
        <button
          onClick={handleCollapseAll}
          className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
          title="Collapse All"
          aria-label="Collapse all tree nodes"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M1 3h14v1H1zM3 7h10v1H3zM5 11h6v1H5z" />
          </svg>
        </button>
      </div>

      {/* Search input */}
      <div className="border-b border-gray-700 px-3 py-2">
        <input
          type="text"
          value={treeFilter}
          onChange={(e) => setTreeFilter(e.target.value)}
          placeholder="Filter tree..."
          className="w-full rounded border border-gray-600 bg-gray-800 px-2 py-1 text-sm text-gray-200 placeholder-gray-500 outline-none focus:border-indigo-500"
          aria-label="Filter tree nodes"
        />
      </div>

      {/* Tree content */}
      <div className="flex-1 overflow-y-auto py-1" role="tree">
        {!appStructure && (
          <div className="px-3 py-4 text-center text-sm text-gray-500">
            No app structure loaded.
          </div>
        )}

        {noResults && (
          <div className="px-3 py-4 text-center text-sm text-gray-500">
            No results for &ldquo;{treeFilter}&rdquo;
          </div>
        )}

        {filteredTree.map((node) => (
          <TreeNodeItem
            key={node.id}
            node={node}
            depth={0}
            filter={treeFilter}
            selectedNodeId={selectedNodeId}
            onSelect={selectNode}
            onToggle={toggleNode}
          />
        ))}
      </div>
    </div>
  );
}
