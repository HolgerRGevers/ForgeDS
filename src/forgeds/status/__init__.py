"""ForgeDS aggregate-health CLI (`forgeds-status`).

Polls config_sanity + db_freshness + toolchain + lint_summary and renders
a single text banner or JSON-v1 status envelope the IDE / CI can poll.
"""
