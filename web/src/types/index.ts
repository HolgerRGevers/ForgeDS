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

export type {
  AccessTable,
  AccessColumn,
  ZohoForm,
  ZohoField,
  FieldMapping,
  TableMapping,
  ValidationResult,
  ValidationDetail,
  UploadState,
  DatabaseStore,
} from "./database";
