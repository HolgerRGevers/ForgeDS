/**
 * TypeScript type definitions for Zoho Creator .ds import files.
 *
 * These interfaces model the declarative .ds format that Zoho Creator
 * uses for application import/export. The emitter in ds-emitter.ts
 * converts these typed objects into .ds text output.
 *
 * Mirrors the Python dataclasses in forgeds/core/build_ds.py.
 */

// ============================================================
// Field type mapping: forms.yaml names → Zoho .ds type names
// ============================================================

export const DS_FIELD_TYPES = [
  "SingleLine",
  "MultiLine",
  "Dropdown",
  "Number",
  "Decimal",
  "Date",
  "DateTime",
  "Email",
  "Checkbox",
  "URL",
  "Phone",
  "Currency",
  "Percent",
  "RichText",
  "File",
  "Image",
  "Audio",
  "Video",
  "Signature",
] as const;

export type DsFieldType = (typeof DS_FIELD_TYPES)[number];

/** Maps forms.yaml type names to Zoho .ds export type names. */
export const TYPE_MAP: Record<DsFieldType, string> = {
  SingleLine: "text",
  MultiLine: "textarea",
  Dropdown: "picklist",
  Number: "number",
  Decimal: "decimal",
  Date: "date",
  DateTime: "datetime",
  Email: "email",
  Checkbox: "checkbox",
  URL: "url",
  Phone: "phone",
  Currency: "currency",
  Percent: "percent",
  RichText: "richtext",
  File: "upload file",
  Image: "image",
  Audio: "audio",
  Video: "video",
  Signature: "signature",
};

// ============================================================
// Application
// ============================================================

export interface DsApplication {
  displayName: string;
  dateFormat: string;
  timeZone: string;
  timeFormat: "12-hr" | "24-hr";
}

// ============================================================
// Forms & Fields
// ============================================================

export interface DsField {
  name: string;
  displayName: string;
  fieldType: DsFieldType;
  required: boolean;
  /** Comma-separated values for Dropdown fields. */
  choices?: string;
}

export interface DsForm {
  linkName: string;
  displayName: string;
  fields: DsField[];
}

// ============================================================
// Reports
// ============================================================

export interface DsReport {
  linkName: string;
  reportType: "list" | "kanban";
  /** Form link name this report queries. */
  form: string;
  displayName: string;
  /** Column definitions: "FieldName as Label, FieldName2 as Label2". */
  columns: string;
  /** Filter expression: "Status == \"Open\" && Days_Remaining > 0". */
  filter?: string;
}

// ============================================================
// Pages (ZML dashboards)
// ============================================================

export interface DsPage {
  linkName: string;
  displayName: string;
  /** ZML content string (escaped for embedding in .ds). */
  content: string;
}

// ============================================================
// Workflows
// ============================================================

export interface DsFormWorkflow {
  linkName: string;
  displayName: string;
  form: string;
  recordEvent: "on add" | "on edit" | "on add or edit";
  eventType: "on success" | "on validate";
  /** Raw Deluge source code. */
  code: string;
}

export interface DsSchedule {
  linkName: string;
  displayName: string;
  form: string;
  /** Raw Deluge source code. */
  code: string;
}

// ============================================================
// Blueprints (workflow state machines)
// ============================================================

export interface DsBlueprintStage {
  name: string;
  displayName: string;
}

export interface DsBlueprintTransition {
  linkName: string;
  displayName: string;
  fromStage: string;
  toStage: string;
}

export interface DsBlueprint {
  linkName: string;
  displayName: string;
  form: string;
  stages: DsBlueprintStage[];
  transitions: DsBlueprintTransition[];
}

// ============================================================
// Menu structure
// ============================================================

export interface DsMenuSection {
  displayName: string;
  icon: string;
  forms?: string[];
  reports?: string[];
  pages?: string[];
}

// ============================================================
// Top-level .ds file structure
// ============================================================

export interface DsFile {
  application: DsApplication;
  forms: DsForm[];
  reports: DsReport[];
  pages: DsPage[];
  workflows: DsFormWorkflow[];
  schedules: DsSchedule[];
  blueprints: DsBlueprint[];
  menuSections: DsMenuSection[];
  roles: string[];
}
