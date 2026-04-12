/** HTTP methods supported by Zoho Custom API Builder */
export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

/** Authentication modes */
export type AuthMode = "oauth2" | "public_key";

/** User scope for API access */
export type UserScope =
  | "admin_only"
  | "selective_users"
  | "all_users"
  | "portal_users";

/** Content type for POST/PUT requests */
export type ContentType = "application/json" | "multipart/form-data";

/** Response type */
export type ResponseType = "standard" | "custom";

/** A parameter definition for the API request */
export interface ApiParameter {
  id: string;
  key: string;
  type: "text" | "number" | "date" | "boolean";
  required: boolean;
  description: string;
}

/** A custom status code mapping */
export interface StatusCodeMapping {
  statusCode: number;
  responseCode: number;
}

/** Complete Custom API definition */
export interface CustomApiDefinition {
  id: string;
  /** Basic Details */
  name: string;
  linkName: string; // URL path segment
  description: string;
  /** Request */
  method: HttpMethod;
  auth: AuthMode;
  userScope: UserScope;
  contentType?: ContentType; // Only for POST/PUT
  parameters: ApiParameter[];
  /** Response */
  responseType: ResponseType;
  statusCodes: StatusCodeMapping[];
  /** Actions */
  application: string;
  namespace: string;
  functionName: string;
  /** Generated code */
  generatedCode: string;
  /** Metadata */
  createdAt: number;
  updatedAt: number;
}

/** Which step of the wizard is active */
export type WizardStep =
  | "basic"
  | "request"
  | "response"
  | "actions"
  | "summary";

/** API page store */
export interface ApiStore {
  // API definitions
  apis: CustomApiDefinition[];
  selectedApiId: string | null;

  // Wizard state
  wizardStep: WizardStep;
  draftApi: CustomApiDefinition | null; // API being created/edited
  isCreating: boolean;

  // Actions
  setApis: (apis: CustomApiDefinition[]) => void;
  selectApi: (id: string | null) => void;

  // Wizard actions
  startCreate: () => void; // Initialize a new draft API
  startEdit: (id: string) => void; // Load existing API into draft
  setWizardStep: (step: WizardStep) => void;
  updateDraft: (updates: Partial<CustomApiDefinition>) => void;
  addParameter: (param: ApiParameter) => void;
  removeParameter: (paramId: string) => void;
  updateParameter: (paramId: string, updates: Partial<ApiParameter>) => void;
  addStatusCode: (mapping: StatusCodeMapping) => void;
  removeStatusCode: (statusCode: number) => void;
  saveDraft: () => void; // Save draft to apis list
  cancelDraft: () => void; // Discard draft
  deleteApi: (id: string) => void;
}
