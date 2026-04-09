// TypeScript interfaces — barrel export
export type {
  BridgeMessage,
  BridgeResponse,
  BridgeStore,
  ConnectionListener,
  ConnectionStatus,
} from "./bridge";

export type {
  RefinedSection,
  RefinedPromptProps,
  PromptInputProps,
} from "./prompt";

export type {
  TreeNode,
  AppStructure,
  EditorTab,
  LintDiagnostic,
  InspectedElementType,
  RelationshipLink,
  InspectorData,
  ConsoleEntry,
  ConsoleTab,
  IdeStore,
} from "./ide";
