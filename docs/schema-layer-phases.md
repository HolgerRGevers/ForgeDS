# Schema Layer — Phase Prompts

## Phase 2: First Consumer Migration (DelugeDB delegates to SchemaRegistry)

```
ULTRATHINK THROUGH THIS STEP BY STEP:

Phase 2 of the ForgeDS schema layer migration. Phase 1 is complete —
`src/forgeds/schema/` exists with types.py, fields.py, relations.py,
constraints.py, registry.py, and __init__.py.

The SchemaRegistry (get_registry()) loads form schemas, FK relationships,
picklist constraints, and NOT NULL constraints from deluge_lang.db,
access_vba_lang.db, and forgeds.yaml. It's tested and working.

Phase 2 goal: Make DelugeDB (in src/forgeds/core/lint_deluge.py) delegate
its form/field/picklist data to get_registry() instead of loading its
own copies from SQLite.

Specifically:
1. In DelugeDB._load_caches(), replace the form_fields loading block
   (lines that query "SELECT form_name, field_link FROM form_fields"
   and build self.form_fields, self.all_known_fields, self.expense_fields)
   with delegation to get_registry().

2. Replace self.valid_statuses (from "SELECT value FROM valid_statuses")
   with reg.valid_statuses().

3. Replace self.valid_actions (from "SELECT value FROM valid_actions")
   with reg.valid_actions().

4. Keep all language-data attributes unchanged: reserved_words,
   zoho_variable_names, function_names, banned_functions,
   banned_variables, banned_function_patterns, banned_variable_patterns,
   sendmail_required, invoke_url_required. These are language semantics,
   not schema.

5. The PUBLIC interface of DelugeDB must stay identical — same attribute
   names, same types (set[str], dict[str, set[str]]). No changes to
   lint_rules.py or any rule functions should be needed.

6. Run the linter against Ten_Chargeback (at
   /mnt/c/Users/holge/OneDrive/Documents/GitHub/Ten_Chargeback/src/deluge/)
   to verify identical output. The expected summary line is:
   "9 files: 45 error(s), 9 warning(s), 0 info"

7. Commit as: feat(schema): migrate DelugeDB form/field/picklist data to SchemaRegistry

After Phase 2, prepare the Phase 3 prompt at the end.
```

## Phase 3: Hybrid Consolidation (HybridDB + ValidatorDB delegate to SchemaRegistry)

```
ULTRATHINK THROUGH THIS STEP BY STEP:

Phase 3 of the ForgeDS schema layer migration. Phases 1-2 are complete:
- Phase 1: src/forgeds/schema/ module created (types, fields, relations,
  constraints, registry)
- Phase 2: DelugeDB delegates form_fields, valid_statuses, valid_actions
  to get_registry()

Phase 3 goal: Migrate HybridDB and ValidatorDB to delegate shared data
to SchemaRegistry, eliminating triple-loading of the same SQLite tables.

Specifically:

1. HybridDB (src/forgeds/hybrid/lint_hybrid.py):
   - Replace _load_deluge_db() method: instead of querying form_fields,
     valid_statuses, valid_actions from SQLite, delegate to get_registry().
   - self.form_fields should come from
     {name: schema.field_names() for name, schema in reg.all_forms().items()}
   - self.form_field_types should come from
     {(name, f.link_name): f.field_type_raw for name, schema in
      reg.all_forms().items() for f in schema.fields.values()}
   - self.valid_statuses = set(reg.valid_statuses())
   - self.valid_actions = set(reg.valid_actions())
   - Keep all Access-specific loading unchanged (_load_access_db).
   - Public interface must stay identical.

2. ValidatorDB (src/forgeds/hybrid/validate_import.py):
   - Replace _load_deluge_db() method similarly.
   - Replace FK_RELATIONSHIPS dict with reg.get_relations() usage.
   - Replace TABLE_TO_FORM dict with reg.table_to_form().
   - Keep _load_access_db() unchanged.

3. If upload_to_creator.py exists and has UPLOAD_ORDER, replace with
   reg.upload_order().

4. Run hybrid linter and validate_import against available test data
   to verify no regressions.

5. Commit as: refactor(schema): migrate HybridDB and ValidatorDB to SchemaRegistry

After Phase 3, prepare the Phase 4 prompt at the end.
```

## Phase 4: Type-Aware Linting (AST type annotations + type checker)

```
ULTRATHINK THROUGH THIS STEP BY STEP:

Phase 4 of the ForgeDS schema layer migration. Phases 1-3 are complete:
- Phase 1: src/forgeds/schema/ module (types, fields, relations,
  constraints, registry)
- Phase 2: DelugeDB delegates to SchemaRegistry
- Phase 3: HybridDB + ValidatorDB delegate to SchemaRegistry

Phase 4 goal: Add type inference to the AST so linters can reason about
types structurally rather than via string matching.

Specifically:

1. Add optional type annotation to AST Expr base class
   (src/forgeds/lang/ast_nodes.py):
   - Add `resolved_type: DelugeType | None = None` field to Expr
   - This is populated post-parse by the type checker, not by the parser

2. Create src/forgeds/compiler/type_checker.py:
   - TypeChecker(ast.Visitor) that walks a parsed Program and populates
     resolved_type on Expr nodes
   - Literal: use LITERAL_KIND_MAP (kind -> DelugeType)
   - Identifier: look up in scope (local assignments) or UNKNOWN
   - FieldAccess on input.*: use reg.field_type(form, field)
   - FormQuery (TableName[criteria]): returns COLLECTION (nullable)
   - FunctionCall: use function return type from DelugeDB if available,
     else ANY
   - BinaryExpr: use result_type(left.resolved_type, op,
     right.resolved_type)
   - Assignment: propagate RHS type to LHS variable in scope

3. Enhance DG005 in compiler/lint_rules.py:
   - After null guard (if var != null), narrow var's type from
     COLLECTION|NULL to COLLECTION in the guarded block
   - Track scope for type narrowing

4. Enhance DG004 to report the expected field type:
   - "Unknown field 'input.amount_zar'. Did you mean 'amount_zar'
     (Decimal)?"

5. Test against Ten_Chargeback and ERM scripts.

6. Commit as: feat(schema): add type inference to AST via TypeChecker visitor

After Phase 4, prepare the Phase 5 prompt at the end.
```

## Phase 5: Cross-Form Validation (FK-aware lint rules)

```
ULTRATHINK THROUGH THIS STEP BY STEP:

Phase 5 of the ForgeDS schema layer migration. Phases 1-4 are complete:
- Phase 1: src/forgeds/schema/ module
- Phase 2: DelugeDB delegates to SchemaRegistry
- Phase 3: HybridDB + ValidatorDB delegate to SchemaRegistry
- Phase 4: AST type inference via TypeChecker

Phase 5 goal: Use the RelationGraph for cross-form validation in lint
rules.

Specifically:

1. New rule DG022: Validate `insert into FormName` targets
   - Check that FormName exists in reg.all_forms()
   - If not, suggest closest match from known forms

2. New rule DG023: FK field reference validation
   - When inserting into a child form, verify FK fields reference
     valid parent forms per the relation graph
   - e.g., insert into Approval_History with claim = X should verify
     that "claim" is an FK to Expense_Claims

3. New rule DG024: Cross-form field access validation
   - For `rec = FormName[criteria]; rec.field_name`, verify that
     field_name exists on FormName's schema
   - Uses FormQuery resolved_type + FieldAccess to trace the form

4. Enhance DG010 (missing required params):
   - Use SchemaRegistry to validate insert block field names against
     the target form's schema, not just sendmail/invokeUrl params

5. Test against both Ten_Chargeback and ERM.

6. Commit as: feat(lint): add cross-form validation rules using SchemaRegistry
```
