/** An Access database table */
export interface AccessTable {
  name: string;
  columns: AccessColumn[];
}

export interface AccessColumn {
  name: string;
  type: string; // Access/Jet SQL type (e.g., "TEXT", "LONG", "CURRENCY", "DATETIME")
  nullable: boolean;
  isPrimaryKey: boolean;
}

/** A Zoho Creator form (target) */
export interface ZohoForm {
  name: string;
  displayName: string;
  fields: ZohoField[];
}

export interface ZohoField {
  linkName: string;
  displayName: string;
  type: string; // Zoho type (e.g., "Text", "Number", "Decimal", "Date", "Lookup")
  required: boolean;
}

/** A mapping between an Access column and a Zoho field */
export interface FieldMapping {
  id: string;
  accessTable: string;
  accessColumn: string;
  accessType: string;
  zohoForm: string;
  zohoField: string;
  zohoType: string;
  /** Mapping status */
  status: "mapped" | "warning" | "error" | "unmapped";
  /** Warning/error message if any */
  statusMessage?: string;
  /** Whether this was auto-mapped or manual */
  isAutoMapped: boolean;
}

/** A table-level mapping (Access table -> Zoho form) */
export interface TableMapping {
  id: string;
  accessTable: string;
  zohoForm: string;
  fieldMappings: FieldMapping[];
  /** Overall status */
  status: "complete" | "partial" | "unmapped";
}

/** Validation result from running lint-hybrid or validate */
export interface ValidationResult {
  id: string;
  timestamp: string;
  tool: "lint-hybrid" | "validate" | "upload";
  status: "pass" | "fail" | "warning";
  summary: string;
  details: ValidationDetail[];
}

export interface ValidationDetail {
  severity: "error" | "warning" | "info";
  rule?: string;
  message: string;
  source?: string; // file or table name
  line?: number;
}

/** Upload progress state */
export interface UploadState {
  status: "idle" | "validating" | "uploading" | "complete" | "error";
  currentTable?: string;
  progress: number; // 0-100
  totalRecords: number;
  uploadedRecords: number;
  errors: string[];
}

/** Database page store */
export interface DatabaseStore {
  // Source data
  accessTables: AccessTable[];
  zohoForms: ZohoForm[];

  // Mappings
  tableMappings: TableMapping[];
  selectedMappingId: string | null;

  // Validation
  validationResults: ValidationResult[];

  // Upload
  uploadState: UploadState;

  // Dropped CSV files
  csvFiles: Array<{ name: string; rowCount: number }>;

  // Actions
  setAccessTables: (tables: AccessTable[]) => void;
  setZohoForms: (forms: ZohoForm[]) => void;
  setTableMappings: (mappings: TableMapping[]) => void;
  selectMapping: (id: string | null) => void;
  updateFieldMapping: (
    mappingId: string,
    fieldMappingId: string,
    updates: Partial<FieldMapping>,
  ) => void;
  addValidationResult: (result: ValidationResult) => void;
  clearValidationResults: () => void;
  setUploadState: (state: Partial<UploadState>) => void;
  addCsvFile: (file: { name: string; rowCount: number }) => void;
  removeCsvFile: (name: string) => void;
}
