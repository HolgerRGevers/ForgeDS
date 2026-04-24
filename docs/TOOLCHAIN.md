# ForgeDS toolchain (Phase 2C)

## Node.js

ForgeDS is Python-first but shells out to Node for ESLint (widget lint)
and ZET (widget bundle). Neither is installed by `pip install forgeds`;
both are **runtime-optional** in the Phase 1 posture — absence triggers
exit code 3 + install hint rather than a hard failure.

- **Minimum version:** Node **≥ 18 LTS**.
- **Recommended:** Node 20 LTS or 22 LTS.

## ESLint

Used by `forgeds-lint-widgets`.

```bash
# Global
npm i -g eslint

# Per-consumer-project
npm i --save-dev eslint
```

Minimum supported: ESLint **8+**.

## Zoho Extension Toolkit (ZET)

Used by `forgeds-bundle-widget` to produce upload-ready widget ZIPs.

```bash
npm install -g zoho-extension-toolkit
# or
npx zoho-extension-toolkit --version
```

**Pinned version (known-good):** currently `zoho-extension-toolkit@1.x`.
CI pins to a specific patch release; see `.github/workflows/ci.yml` if
this repo publishes one.

**`--no-zet` fallback:** `forgeds-bundle-widget --no-zet` uses stdlib
`zipfile.ZipFile` to produce the same ZIP layout. The spec §6.4 flags
this UNVERIFIED until the §7.5 research spike confirms byte-for-byte
parity with `zet pack`. Until then, `--no-zet` is documented-beta —
functional for iteration, but may produce bundles that behave subtly
differently in the Creator runtime.

**Vendored-ZET contingency:** if upstream ZET proves unstable, the plan
allows vendoring a known-good release at `tools/zet-vendor/` and
shelling to it via the `FORGEDS_ZET_PATH` env var. Not default
behavior; contingency only.

## Python

ForgeDS itself: Python **≥ 3.10**, stdlib-only. No `pyodbc`, no
`jsonschema`, no `requests` — all replaced by stdlib equivalents or
inline validators.

## Regeneration commands

```bash
# Language DBs (Deluge + Access/VBA)
forgeds-build-db
forgeds-build-access-db

# Widget SDK database + mock (Phase 2B)
forgeds-build-widget-db
forgeds-gen-sdk-mock

# Widget lint / runtime (Phase 1 / 2B)
forgeds-lint-widgets <widget-root>
forgeds-run-widget   <widget-name>

# Widget build pipeline (Phase 2C)
forgeds-scaffold-widget --spec widget-spec.yaml --output src/widgets/
forgeds-bundle-widget   --widget expense_dashboard --no-zet
forgeds-deploy-widget   --widget expense_dashboard --dry-run \
                        --target creator:app-id=<id>
forgeds-build-app       --plan-only     # until orchestrator ships
```
