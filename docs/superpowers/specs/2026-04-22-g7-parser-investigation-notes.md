# G7 — .ds parser investigation notes

**Date:** 2026-04-22

## Question
Does `.ds` carry widget references or blobs?

## Method
- Grep `tests/fixtures/*.ds` for tokens: `widget`, `plugin`, `script-source`
- Inspect any matches for context

## Findings

No matches. `.ds` exports do not carry widget references. Widgets are packaged
separately as zip blobs (manifest + JS/HTML/CSS) and uploaded via the Creator
portal. `parse_ds_export.py` needs no changes.

## Decision

No code changes to `parse_ds_export.py`. Widget declarations live in
`forgeds.yaml` under the `widgets:` block, and on disk under each widget's
configured `root`. `forgeds-lint-hybrid` surfaces widget↔Deluge relationships
through `WG###` rules against the config, not by parsing `.ds`.
