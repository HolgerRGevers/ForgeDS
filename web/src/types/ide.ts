// === App Tree Explorer Types ===

/** A node in the application structure tree */
export interface TreeNode {
  id: string;
  label: string;
  type:
    | "application"
    | "form"
    | "field"
    | "workflow"
    | "report"
    | "page"
    | "schedule"
    | "api"
    | "section";
  children?: TreeNode[];
  /** For fields: the Deluge/Zoho field type */
  fieldType?: string;
  /** For workflows: the trigger event */
  trigger?: string;
  /** The .dg or .ds file path this node maps to, if any */
  filePath?: string;
  /** Whether this node is expanded in the tree */
  isExpanded?: boolean;
  /** Metadata for the inspector */
  metadata?: Record<string, unknown>;
}

/** Parsed application structure from a .ds export */
export interface AppStructure {
  name: string;
  displayName: string;
  tree: TreeNode[];
  /** Flat lookup: node ID -> TreeNode for fast access */
  nodeIndex: Map<string, TreeNode>;
  /** How this structure was loaded */
  enrichmentLevel?: "local" | "bridge-enriched";
}

// === Editor Types ===

/** An open file tab in the editor */
export interface EditorTab {
  id: string;
  name: string;
  path: string;
  content: string;
  language: string;
  isDirty: boolean;
  /** Cursor position */
  cursorLine?: number;
  cursorColumn?: number;
}

/** A lint diagnostic for inline display */
export interface LintDiagnostic {
  file: string;
  line: number;
  rule: string;
  severity: "error" | "warning" | "info";
  message: string;
}

// === Inspector Panel Types ===

/** What kind of element is being inspected */
export type InspectedElementType =
  | "field"
  | "function"
  | "form"
  | "variable"
  | "none";

/** A relationship link to another element */
export interface RelationshipLink {
  targetId: string;
  targetLabel: string;
  targetType: string;
  relationship: string; // e.g., "used in", "belongs to", "references"
}

/** Data shown in the Inspector panel */
export interface InspectorData {
  type: InspectedElementType;
  name: string;
  /** Key-value metadata pairs */
  properties: Array<{ label: string; value: string }>;
  /** Relationship links to other elements */
  relationships: RelationshipLink[];
  /** Usage locations (file:line references) */
  usages: Array<{ file: string; line: number; context: string }>;
  /** For functions: parameter info */
  signature?: string;
  /** For functions: description */
  description?: string;
}

// === Dev Console Types ===

/** A single entry in the dev console */
export interface ConsoleEntry {
  id: string;
  timestamp: string;
  type: "lint" | "build" | "info" | "error" | "ai";
  message: string;
  /** For lint entries: rule ID and file location */
  rule?: string;
  file?: string;
  line?: number;
  severity?: "error" | "warning" | "info";
}

/** Active tab in the dev console */
export type ConsoleTab = "lint" | "build" | "relationships" | "ai";

// === Shell Overhaul Types ===

/** A sub-tab within the Scripts category of the bottom console. */
export type ScriptsTab =
  | "complete"
  | "form-workflows"
  | "schedules"
  | "approvals"
  | "payments"
  | "blueprints"
  | "batch-workflows"
  | "functions";

/** A top-level category in the bottom console (two-level tab structure). */
export type ConsoleCategory = "scripts" | "devtools";

/** Remembered drop location for a panel hidden via the activity bar.
 *  Used when re-adding the panel so it returns to where the user last had it. */
export interface PanelDockHint {
  referencePanelId?: string;
  direction?: "left" | "right" | "above" | "below" | "within";
}

/** How the currently-loaded app arrived. Drives first-load UI behavior. */
export type AppLoadSource = "wizard" | "repo" | "upload" | "bridge-auto" | null;

// === IDE Store Types ===

export interface IdeStore {
  // App tree
  appStructure: AppStructure | null;
  selectedNodeId: string | null;
  treeFilter: string;

  // Editor
  tabs: EditorTab[];
  activeTabId: string | null;
  diagnostics: LintDiagnostic[];

  // Inspector
  inspectorData: InspectorData | null;

  // Dev console / Bottom panel
  consoleEntries: ConsoleEntry[];
  activeConsoleCategory: ConsoleCategory;
  activeScriptsTab: ScriptsTab;
  activeDevToolsTab: ConsoleTab;

  // App acquisition tracking (drives first-load UI)
  appLoadSource: AppLoadSource;
  completeScriptShownForApps: Set<string>;

  // Actions
  loadAppStructure: (structure: AppStructure) => void;
  selectNode: (nodeId: string) => void;
  toggleNode: (nodeId: string) => void;
  setTreeFilter: (filter: string) => void;

  loadGeneratedFiles: (files: Array<{ name: string; path: string; content: string; language: string }>) => void;
  openTab: (tab: EditorTab) => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  updateTabContent: (tabId: string, content: string) => void;
  setDiagnostics: (diagnostics: LintDiagnostic[]) => void;

  setInspectorData: (data: InspectorData | null) => void;

  addConsoleEntry: (entry: Omit<ConsoleEntry, "id" | "timestamp">) => void;
  clearConsole: () => void;
  setActiveConsoleCategory: (cat: ConsoleCategory) => void;
  setActiveScriptsTab: (tab: ScriptsTab) => void;
  setActiveDevToolsTab: (tab: ConsoleTab) => void;

  setAppLoadSource: (src: AppLoadSource) => void;
  markCompleteScriptShown: (appName: string) => void;
}
