# Widget deploy rollback procedure (manual)

ForgeDS does **not** automate rollback of a bad Creator widget
deployment. The Zoho API surface does not cleanly support "unpublish
version N" without also removing the widget entirely, so automating it
would risk data loss. This doc walks through the manual procedure.

## Scope

Applies to deployments performed via `forgeds-deploy-widget --confirm`
(once the §7.5 research spike lands). Pre-spike `--dry-run`
deployments never touch the server and do not need rollback.

## Procedure

### 1. Revert source control

The bad widget code is still in git. Revert the commit(s) that shipped
it:

```bash
git log --oneline src/widgets/<widget-name>/
# identify the commit(s) to revert
git revert <bad-sha>
```

If the widget version bump lives in the same commit, the revert will
also restore the prior `plugin-manifest.json` `version` field.

### 2. Bump version

If multiple deploys share a version string, Zoho may cache the bad
artifact. Bump `plugin-manifest.json`'s `version` field one patch
higher than the current (post-revert) value:

```json
{
  "version": "0.0.2"
}
```

### 3. Rebuild + redeploy

```bash
forgeds-bundle-widget  --widget <widget-name> --no-zet
forgeds-deploy-widget  --widget <widget-name> \
                       --target creator:app-id=<app-id> \
                       --confirm
```

Confirm the upload succeeded by opening the widget in Creator; the
post-deploy `widget-spec.yaml` `deployment:` block will have the new
`last_uploaded_version` recorded.

### 4. Verify consumers

If the widget is embedded in any form / report, refresh those pages
and confirm the bad behaviour is gone.

## What if the widget is blocking form render?

If the bad widget is visible in Creator and preventing users from
working:

1. In Creator's widget manager, remove the widget from the form
   temporarily (this is a manual UI step; ForgeDS cannot do it).
2. Follow the rollback procedure above.
3. Re-add the widget to the form.

This is unpleasant but unavoidable pre-spike. A future phase may
automate the remove/re-add cycle.

## Prevention

- **Always deploy with `--dry-run` first.** The default dry-run mode
  shows the target URL + redacted OAuth source + ZIP size; inspect
  before `--confirm`.
- **Don't combine `--force` on scaffold with imminent deploy.** The
  scaffolder emits SCF002 per overwritten file, but a `--force` run
  will still clobber hand-edited code. Separate scaffolds from
  deploys by at least one commit.
- **Consider staging.** Until Phase 2E lands the multi-environment
  orchestration, you can manually maintain two separate targets
  (`creator:app-id=staging-...` and `creator:app-id=prod-...`) and
  deploy to staging first.
