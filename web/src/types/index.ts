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

export type {
  HttpMethod,
  AuthMode,
  UserScope,
  ContentType,
  ResponseType,
  ApiParameter,
  StatusCodeMapping,
  CustomApiDefinition,
  WizardStep,
  ApiStore,
} from "./api";

export type {
  GitHubUser,
  RepoInfo,
  GitTreeNode,
  FileChange,
  CommitInfo,
  BranchInfo,
  DeviceCodeResponse,
  AuthStatus,
  AuthStore,
  RepoStore,
} from "./github";
