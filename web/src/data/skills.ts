/**
 * Curated skills library for the ForgeDS IDE prompt system.
 *
 * Each skill provides a system prompt fragment that gets prepended to the
 * user's prompt when activated, guiding the AI's behavior for specific domains.
 */

export interface Skill {
  id: string;
  name: string;
  category: SkillCategory;
  description: string;
  systemPrompt: string;
  examplePrompts: string[];
  tags: string[];
  source: SkillSource;
}

export type SkillSource = "built-in" | "community" | "marketplace" | "github";

export type SkillCategory =
  | "strategic-thinking"
  | "process-design"
  | "prompt-engineering"
  | "ms-access"
  | "sql"
  | "databases"
  | "apis"
  | "data-integration"
  | "general";

export interface SkillCategoryInfo {
  id: SkillCategory;
  label: string;
  icon: string;
  description: string;
}

export const SKILL_CATEGORIES: SkillCategoryInfo[] = [
  {
    id: "strategic-thinking",
    label: "Strategic Thinking",
    icon: "\u{1F3AF}",
    description: "Business analysis, decision frameworks, and strategic planning",
  },
  {
    id: "process-design",
    label: "Process Design",
    icon: "\u{1F504}",
    description: "Workflow modeling, automation patterns, and process optimization",
  },
  {
    id: "prompt-engineering",
    label: "Prompt Engineering",
    icon: "\u{1F9E0}",
    description: "Meta-prompts, chain-of-thought, and structured output patterns",
  },
  {
    id: "ms-access",
    label: "MS Access",
    icon: "\u{1F4CA}",
    description: "Access database analysis, VBA patterns, and migration strategies",
  },
  {
    id: "sql",
    label: "SQL",
    icon: "\u{1F5C4}\uFE0F",
    description: "Query optimization, schema design, and SQL translation",
  },
  {
    id: "databases",
    label: "Databases",
    icon: "\u{1F4BE}",
    description: "Data modeling, normalization, and relationship mapping",
  },
  {
    id: "apis",
    label: "APIs",
    icon: "\u{1F310}",
    description: "REST design, OAuth flows, webhooks, and API documentation",
  },
  {
    id: "data-integration",
    label: "Data Integration",
    icon: "\u{1F517}",
    description: "ETL patterns, data validation, and import/export pipelines",
  },
];

export const SKILLS: Skill[] = [
  // ── Design Language ────────────────────────────────────────────────────
  {
    id: "forgeds-design-language",
    name: "ForgeDS Design Language",
    category: "general",
    description: "Apply the ForgeDS design language to generated Zoho Creator apps: naming conventions, form layout, workflow structure, color themes, and dashboard patterns",
    systemPrompt:
      "Apply the ForgeDS Design Language to all generated code and configuration. " +
      "Form design: key identifiers first, then data fields, then audit fields (Added_User, Modified_Time) last. " +
      "Section naming: title case, max 3 words. Field display names: Title Case with spaces (e.g. 'Amount ZAR'). " +
      "Field link names: snake_case (e.g. Amount_ZAR). " +
      "Workflow naming: form_name.trigger_event.dg. Always include a header comment with form name, trigger, and purpose. " +
      "Null guards: always wrap lookups with if (result != null && result.count() > 0). " +
      "Audit fields: set Added_User = zoho.loginuser on create, never trust user input for audit data. " +
      "Reports: default sort most recent first, SUM for currency, COUNT for records. " +
      "Dashboards: top row = 3-4 KPI cards, middle = primary chart, bottom = secondary views. " +
      "Color conventions: Draft=gray, Pending=yellow, Approved=green, Rejected=red. " +
      "Zoho theme primary color: #2563eb. " +
      "Code style: lowercase snake_case variables, descriptive function names, inline comments for complex logic only.",
    examplePrompts: [
      "Generate an expense claim form following ForgeDS conventions",
      "Create a dashboard layout for project management",
      "Build a multi-level approval workflow with proper naming",
    ],
    tags: ["design", "conventions", "naming", "layout", "zoho"],
    source: "built-in",
  },

  // ── Strategic Thinking ──────────────────────────────────────────────────
  {
    id: "swot-analysis",
    name: "SWOT Analysis",
    category: "strategic-thinking",
    description: "Analyze strengths, weaknesses, opportunities, and threats for app decisions",
    systemPrompt:
      "Apply SWOT analysis to evaluate decisions. For each option, identify Strengths (internal advantages), Weaknesses (internal limitations), Opportunities (external possibilities), and Threats (external risks). Present findings in a structured matrix and provide a recommendation based on the analysis.",
    examplePrompts: [
      "Should we migrate our expense tracking from Access to Zoho Creator?",
      "Evaluate adding a custom API vs using Zoho's built-in connectors",
    ],
    tags: ["business", "analysis", "decision-making"],
    source: "built-in",
  },
  {
    id: "requirements-decomposition",
    name: "Requirements Decomposition",
    category: "strategic-thinking",
    description: "Break complex requirements into atomic, implementable user stories",
    systemPrompt:
      "Decompose requirements using the INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable). Break each requirement into user stories with acceptance criteria. Identify dependencies between stories and suggest an implementation order that minimizes risk.",
    examplePrompts: [
      "Break down an employee reimbursement system into implementable features",
      "Decompose a multi-department approval workflow requirement",
    ],
    tags: ["requirements", "planning", "agile"],
    source: "built-in",
  },
  {
    id: "value-chain-analysis",
    name: "Value Chain Analysis",
    category: "strategic-thinking",
    description: "Map business processes to identify where automation adds the most value",
    systemPrompt:
      "Analyze the business value chain to identify high-impact automation opportunities. Map primary activities (inbound, operations, outbound, marketing, service) and support activities (infrastructure, HR, technology, procurement). Prioritize automation targets by effort vs. impact. Focus on areas where Zoho Creator forms, workflows, and integrations can eliminate manual steps.",
    examplePrompts: [
      "Where should we automate first in our procurement process?",
      "Map the value chain for our client onboarding flow",
    ],
    tags: ["business", "automation", "value"],
    source: "built-in",
  },

  // ── Process Design ──────────────────────────────────────────────────────
  {
    id: "workflow-modeler",
    name: "Workflow Modeler",
    category: "process-design",
    description: "Design Zoho Creator workflows with triggers, conditions, and actions",
    systemPrompt:
      "Design workflows using Zoho Creator's trigger model: on_create, on_edit, on_validate, on_approval, on_delete, scheduled. For each workflow, specify: trigger event, guard conditions (if-checks), field updates, notifications (sendmail), and any cross-form lookups. Use Deluge syntax for all code snippets. Always validate input with ifnull() guards.",
    examplePrompts: [
      "Design an approval workflow for purchase orders over $5000",
      "Create a workflow that syncs employee data between two forms on update",
    ],
    tags: ["workflow", "automation", "triggers"],
    source: "built-in",
  },
  {
    id: "approval-process-designer",
    name: "Approval Process Designer",
    category: "process-design",
    description: "Design multi-level approval chains with escalation and delegation",
    systemPrompt:
      "Design approval processes for Zoho Creator. Consider: approval levels (single, sequential, parallel), role-based routing, escalation rules (time-based auto-approve or escalate), delegation during absence, audit trail requirements, and notification at each stage. Generate the on_approval and on_validate Deluge scripts with proper status field management.",
    examplePrompts: [
      "Design a 3-level expense approval: manager -> finance -> CFO",
      "Create an approval process with auto-escalation after 48 hours",
    ],
    tags: ["approval", "workflow", "escalation"],
    source: "built-in",
  },
  {
    id: "bpmn-to-deluge",
    name: "BPMN to Deluge",
    category: "process-design",
    description: "Translate BPMN process diagrams into Zoho Creator Deluge scripts",
    systemPrompt:
      "Translate BPMN process descriptions into Zoho Creator implementations. Map BPMN elements: Start Event -> on_create trigger, User Task -> form with workflow, Service Task -> Deluge function, Gateway (XOR) -> if/else, Gateway (AND) -> parallel field updates, End Event -> status update. Generate complete Deluge scripts for each task with proper error handling.",
    examplePrompts: [
      "Convert this purchase requisition BPMN flow into Deluge",
      "Implement a leave request process from BPMN diagram",
    ],
    tags: ["bpmn", "process", "translation"],
    source: "community",
  },

  // ── Prompt Engineering ──────────────────────────────────────────────────
  {
    id: "chain-of-thought",
    name: "Chain of Thought",
    category: "prompt-engineering",
    description: "Structure prompts for step-by-step reasoning and complex problem solving",
    systemPrompt:
      "Use chain-of-thought reasoning: break the problem into explicit steps, think through each step before generating code. For Deluge code generation: 1) Identify the data model (forms, fields, types), 2) Map relationships (lookups, subforms), 3) Define validation rules, 4) Write workflow logic, 5) Add error handling. Show your reasoning at each step.",
    examplePrompts: [
      "Think through the data model for a project management app",
      "Step by step, design the field validation for a financial form",
    ],
    tags: ["reasoning", "structured", "systematic"],
    source: "built-in",
  },
  {
    id: "few-shot-deluge",
    name: "Few-Shot Deluge Patterns",
    category: "prompt-engineering",
    description: "Use example-driven generation with proven Deluge code patterns",
    systemPrompt:
      "Generate Deluge code using established patterns. For lookups: use `zoho.creator.getRecords()` with criteria. For emails: use `sendmail` with proper field substitution. For validations: always check `ifnull(input.FieldName, \"\")` before processing. For calculations: use `zoho.currentdate` for date operations. Match the coding style: lowercase snake_case for variables, descriptive function names, inline comments for complex logic.",
    examplePrompts: [
      "Generate a lookup function that finds the manager for a department",
      "Create a calculation workflow following Deluge best practices",
    ],
    tags: ["patterns", "examples", "best-practices"],
    source: "built-in",
  },
  {
    id: "structured-output",
    name: "Structured Output",
    category: "prompt-engineering",
    description: "Generate code with consistent structure: forms, fields, workflows, reports",
    systemPrompt:
      "Generate output in a consistent structure. For each form: list all fields with types, then all workflows with trigger types, then reports. Use this format for each file: header comment with form name and purpose, field declarations, workflow functions (on_validate first, then on_create, on_edit), helper functions last. Always include the form's link name in comments.",
    examplePrompts: [
      "Generate a complete employee form with all workflows structured consistently",
      "Create the full file structure for a multi-form application",
    ],
    tags: ["structure", "consistency", "organization"],
    source: "built-in",
  },

  // ── MS Access ───────────────────────────────────────────────────────────
  {
    id: "access-schema-analyzer",
    name: "Access Schema Analyzer",
    category: "ms-access",
    description: "Analyze Access database schemas and suggest Zoho Creator equivalents",
    systemPrompt:
      "Analyze MS Access database schemas and map them to Zoho Creator. For each Access table: identify primary keys, foreign keys, data types, and constraints. Map Access types to Zoho: Text->Single Line, Memo->Multi Line, Currency->Decimal, Yes/No->Checkbox, Date/Time->Date-Time, AutoNumber->Auto Number, OLE Object->File Upload. Flag potential data loss (e.g., Access Memo > 50K chars). Suggest lookup fields for foreign key relationships.",
    examplePrompts: [
      "Analyze this Access table structure and suggest Zoho Creator forms",
      "Map these Access foreign keys to Zoho Creator lookup fields",
    ],
    tags: ["access", "migration", "schema"],
    source: "built-in",
  },
  {
    id: "vba-to-deluge",
    name: "VBA to Deluge Translator",
    category: "ms-access",
    description: "Translate VBA macros and modules into Deluge scripts",
    systemPrompt:
      "Translate VBA code to Deluge. Key mappings: VBA Sub/Function -> Deluge function, VBA DoCmd.OpenForm -> Zoho Creator form, VBA Recordset -> getRecords(), VBA DLookup -> fetch via criteria, VBA MsgBox -> info/alert, VBA Error handling -> try-catch not available in Deluge (use ifnull guards instead). Preserve the business logic while adapting to Zoho Creator's event-driven model.",
    examplePrompts: [
      "Convert this VBA event handler to a Deluge on_validate script",
      "Translate this VBA report generation module to Deluge",
    ],
    tags: ["vba", "migration", "translation"],
    source: "built-in",
  },
  {
    id: "access-query-migrator",
    name: "Access Query Migrator",
    category: "ms-access",
    description: "Convert Access SQL queries and crosstabs to Zoho Creator reports",
    systemPrompt:
      "Convert MS Access queries to Zoho Creator equivalents. Access SELECT queries -> Zoho Creator Reports with filters. Access crosstab queries -> Zoho pivot reports or custom Deluge aggregations. Access action queries (UPDATE/INSERT/DELETE) -> Deluge workflows with getRecords() and update/insert operations. Access parameter queries -> Zoho Creator reports with runtime filters. Preserve query logic and handle Access-specific SQL syntax (IIf, Nz, Format).",
    examplePrompts: [
      "Convert this Access crosstab query to a Zoho Creator report",
      "Migrate these Access action queries to Deluge update workflows",
    ],
    tags: ["access", "queries", "reports"],
    source: "community",
  },

  // ── SQL ─────────────────────────────────────────────────────────────────
  {
    id: "sql-optimizer",
    name: "SQL Query Optimizer",
    category: "sql",
    description: "Optimize SQL queries and translate to efficient Zoho Creator data operations",
    systemPrompt:
      "Optimize data access patterns for Zoho Creator. Zoho Creator uses getRecords() with criteria strings, not raw SQL. Optimize by: minimizing API calls (batch lookups), using specific criteria to reduce result sets, avoiding N+1 query patterns (fetch related records in bulk), caching repeated lookups in map variables. For complex joins, use intermediate collections with Deluge maps.",
    examplePrompts: [
      "Optimize this multi-table lookup that runs on every record",
      "Rewrite this nested loop pattern to use batch fetching",
    ],
    tags: ["optimization", "performance", "queries"],
    source: "built-in",
  },
  {
    id: "schema-designer",
    name: "Schema Designer",
    category: "sql",
    description: "Design normalized database schemas with proper field types and constraints",
    systemPrompt:
      "Design database schemas following normalization principles (1NF, 2NF, 3NF) adapted for Zoho Creator. Use lookup fields for foreign keys, subforms for one-to-many relationships, and multi-select lookups for many-to-many. Define field types precisely: Single Line (255 chars), Multi Line (50K chars), Number (no decimals), Decimal (with precision), Currency (2 decimal places). Add mandatory field constraints, unique fields, and display name conventions.",
    examplePrompts: [
      "Design a normalized schema for an inventory management system",
      "Create the form structure for a CRM with contacts, companies, and deals",
    ],
    tags: ["schema", "normalization", "design"],
    source: "built-in",
  },
  {
    id: "sql-to-zoho",
    name: "SQL to Zoho Query",
    category: "sql",
    description: "Translate SQL SELECT/INSERT/UPDATE to Zoho Creator Deluge operations",
    systemPrompt:
      "Translate SQL operations to Zoho Creator Deluge: SELECT -> zoho.creator.getRecords(appOwner, appName, formName, criteria, startIndex, limit). INSERT -> zoho.creator.createRecord(appOwner, appName, formName, dataMap). UPDATE -> zoho.creator.updateRecord(appOwner, appName, formName, criteria, dataMap). DELETE -> use Deluge deleteRecord(). Criteria strings use Zoho syntax: (field == value && field2 != value2). Date comparisons use specific format.",
    examplePrompts: [
      "Convert SELECT * FROM employees WHERE dept='Sales' AND salary > 50000",
      "Translate this INSERT INTO with subquery to Deluge createRecord",
    ],
    tags: ["sql", "translation", "deluge"],
    source: "built-in",
  },

  // ── Databases ───────────────────────────────────────────────────────────
  {
    id: "erd-designer",
    name: "ERD Designer",
    category: "databases",
    description: "Design entity-relationship diagrams and translate to Zoho Creator forms",
    systemPrompt:
      "Design entity-relationship models for Zoho Creator. Entities -> Forms, Attributes -> Fields, Relationships -> Lookup fields or Subforms. For 1:1 relationships, use lookup fields. For 1:N, use subforms or lookup fields with related lists. For M:N, create a junction form with two lookup fields. Always include: primary identifier (Auto Number), audit fields (Added_User, Added_Time, Modified_User, Modified_Time), and status fields where applicable.",
    examplePrompts: [
      "Design the ERD for a hospital patient management system",
      "Map these entities and relationships to Zoho Creator forms",
    ],
    tags: ["erd", "data-modeling", "relationships"],
    source: "built-in",
  },
  {
    id: "data-migration-planner",
    name: "Data Migration Planner",
    category: "databases",
    description: "Plan data migration strategies with rollback and validation checkpoints",
    systemPrompt:
      "Plan data migrations with these phases: 1) Schema mapping (source -> target field mapping), 2) Data cleansing (identify and fix data quality issues), 3) Transformation rules (type conversions, value mappings, concatenations), 4) Load order (respect foreign key dependencies), 5) Validation (row counts, checksum comparison, sample spot-checks), 6) Rollback plan. Use ForgeDS tools: forgeds-validate for pre-migration checks, forgeds-upload for the actual migration.",
    examplePrompts: [
      "Plan the migration of 50 Access tables to Zoho Creator",
      "Create a rollback strategy for our customer data migration",
    ],
    tags: ["migration", "planning", "strategy"],
    source: "built-in",
  },
  {
    id: "seed-data-generator",
    name: "Seed Data Generator",
    category: "databases",
    description: "Generate realistic test data for Zoho Creator forms",
    systemPrompt:
      "Generate realistic seed data for Zoho Creator forms in CSV format. For each form, create 10-50 rows of realistic test data matching field types and constraints. Use realistic names, email addresses, dates (within the last 2 years), currency values (appropriate ranges), and status values (matching picklist options). Ensure referential integrity across related forms. Include edge cases: null optional fields, maximum length strings, boundary dates.",
    examplePrompts: [
      "Generate 20 rows of test data for an employee form with department lookup",
      "Create seed data for an invoice system with line items",
    ],
    tags: ["testing", "seed-data", "csv"],
    source: "community",
  },

  // ── APIs ────────────────────────────────────────────────────────────────
  {
    id: "rest-api-designer",
    name: "REST API Designer",
    category: "apis",
    description: "Design RESTful Custom APIs for Zoho Creator with proper endpoints",
    systemPrompt:
      "Design REST APIs following Zoho Creator's Custom API framework. Each API function maps to one endpoint. Use proper HTTP methods: GET for reads, POST for creates, PUT for updates, DELETE for removes. Define request parameters (query params or JSON body), response format (standard or custom JSON), authentication (OAuth2 or Public Key), and error responses. Generate the Deluge function code with proper input validation, error handling, and response formatting.",
    examplePrompts: [
      "Design a REST API for external systems to query our order status",
      "Create CRUD API endpoints for the customer management form",
    ],
    tags: ["api", "rest", "design"],
    source: "built-in",
  },
  {
    id: "oauth-flow-builder",
    name: "OAuth Flow Builder",
    category: "apis",
    description: "Implement OAuth 2.0 flows for Zoho Creator API integrations",
    systemPrompt:
      "Implement OAuth 2.0 integration with Zoho Creator. Cover: authorization code flow (for web apps), client credentials flow (for server-to-server), refresh token management. Generate the Deluge invokeUrl() calls with proper headers, handle token expiry with automatic refresh, store tokens securely in Zoho Creator fields or connections. Include rate-limit handling (429 responses) with exponential backoff.",
    examplePrompts: [
      "Set up OAuth2 integration with a third-party payment system",
      "Implement automatic token refresh for our Zoho API connection",
    ],
    tags: ["oauth", "authentication", "integration"],
    source: "built-in",
  },
  {
    id: "webhook-handler",
    name: "Webhook Handler",
    category: "apis",
    description: "Create webhook endpoints in Zoho Creator to receive external events",
    systemPrompt:
      "Create webhook handlers using Zoho Creator Custom APIs. Design the endpoint to: validate the incoming payload (check required fields, verify signatures if applicable), parse the JSON body, map external data to Zoho Creator fields, create or update records, and return appropriate HTTP status codes. Include logging for debugging and idempotency checks (prevent duplicate processing using a unique event ID).",
    examplePrompts: [
      "Create a webhook to receive Stripe payment notifications",
      "Build a webhook handler for GitHub commit events",
    ],
    tags: ["webhook", "events", "integration"],
    source: "community",
  },

  // ── Data Integration ────────────────────────────────────────────────────
  {
    id: "etl-pipeline-designer",
    name: "ETL Pipeline Designer",
    category: "data-integration",
    description: "Design extract-transform-load pipelines for Zoho Creator data",
    systemPrompt:
      "Design ETL pipelines for Zoho Creator: Extract (read from source via CSV import, API calls, or direct database connection), Transform (clean, validate, map field names, convert types, apply business rules), Load (use forgeds-upload or Zoho Creator's import API). Handle errors gracefully: log failures, continue processing, generate error reports. For large datasets, implement batch processing with progress tracking.",
    examplePrompts: [
      "Design an ETL pipeline to import monthly sales data from Excel",
      "Create a nightly sync pipeline between our ERP and Zoho Creator",
    ],
    tags: ["etl", "pipeline", "automation"],
    source: "built-in",
  },
  {
    id: "data-validator",
    name: "Data Validator",
    category: "data-integration",
    description: "Create comprehensive data validation rules for import pipelines",
    systemPrompt:
      "Design data validation rules for import pipelines. Check: field length constraints (Single Line: 255, Multi Line: 50K), type compatibility (dates in correct format, numbers without text), required field presence, referential integrity (lookup values exist in parent forms), picklist value validity, email format, phone format, currency precision. Use ForgeDS's Diagnostic system: Severity.ERROR for blocking issues, Severity.WARNING for data quality concerns, Severity.INFO for informational notes.",
    examplePrompts: [
      "Create validation rules for importing customer records from CSV",
      "Design a data quality check for financial transaction imports",
    ],
    tags: ["validation", "quality", "rules"],
    source: "built-in",
  },
  {
    id: "csv-transformer",
    name: "CSV Transformer",
    category: "data-integration",
    description: "Transform CSV data between Access export format and Zoho Creator import format",
    systemPrompt:
      "Transform CSV data for Zoho Creator import. Handle: column renaming (Access field names -> Zoho field names), type conversions (Access date format -> Zoho date format yyyy-MM-dd), value mapping (Access boolean Yes/No -> Zoho checkbox true/false), null handling (Access empty strings -> Zoho empty), encoding issues (ensure UTF-8), special character escaping in CSV. Generate Python scripts using only stdlib (csv module, no pandas) per ForgeDS conventions.",
    examplePrompts: [
      "Transform this Access CSV export for Zoho Creator import",
      "Create a column mapping and transformation script for employee data",
    ],
    tags: ["csv", "transformation", "mapping"],
    source: "built-in",
  },
];
