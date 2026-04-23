# G7 — .ds parser investigation notes

**Date:** 2026-04-22
**Worker:** worker/A5-parser-investigation

## Question
Does `.ds` carry widget references or blobs?

## Method
Grepped `tests/fixtures/*.ds` (and fixture subdirs) for tokens: `widget`,
`plugin`, `script-source`. Inspected matches for context.

Fixture `.ds` files covered (7 total):
- `tests/fixtures/validate_ds_good.ds`
- `tests/fixtures/validate_ds_bad.ds`
- `tests/fixtures/zia-stress-test/enhanced_output.ds`
- `tests/fixtures/zia-stress-test/Expense_Claim_Approval.ds`
- `tests/fixtures/zia-stress-test/Incident_Report_Synchronization.ds`
- `tests/fixtures/zia-stress-test/Invoice_Overdue_Management.ds`
- `tests/fixtures/zia-stress-test/Purchase_Order_Processing.ds`

No `apps/` directory exists in the repo; no additional fixture sources to
scan. The `tests/fixtures/scheduled/` subdir contains only `.dg` (not `.ds`).

## Raw grep output

```
$ grep -l -i -E "widget|plugin|script-source" tests/fixtures/*.ds
(no output; exit code 1 — no matches)

$ grep -i -n -E "widget|plugin|script-source" tests/fixtures/validate_ds_good.ds | head -30
(no output; exit code 0 — no matches)

$ grep -i -n -E "widget|plugin|script-source" tests/fixtures/validate_ds_bad.ds | head -30
(no output; exit code 0 — no matches)

$ grep -l -i -E "widget|plugin|script-source" -r tests/fixtures --include="*.ds"
(no output; exit code 1 — no matches across all 7 .ds fixtures)
```

## Findings

### Branch A — no matches (expected):
`.ds` exports do NOT carry widget references. Widgets are packaged separately
as zip blobs (manifest + JS/HTML/CSS) uploaded through the Creator portal.
`parse_ds_export.py` needs no changes for Phase 1. Document in CLAUDE.md
under ".ds file format gotchas" that widgets live outside .ds.

## Decision
**No code changes in Phase 1.** `parse_ds_export.py` is left untouched.
Widgets are treated as out-of-band artifacts packaged and uploaded separately
from the `.ds` application export.

If a future Creator export format change introduces inline widget references
or embedded blobs, revisit this decision and promote parser work into a
later phase.
