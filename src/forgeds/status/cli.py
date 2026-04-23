"""forgeds-status CLI entry point."""

from __future__ import annotations

import argparse
import sys

from forgeds._shared.output_format import UnknownFormatError, resolve_format
from forgeds.status.checks import StatusCheck, config_sanity, db_freshness, lint_summary, toolchain
from forgeds.status.report import exit_code, render_json, render_text


def _run_all_checks(args) -> list[StatusCheck]:
    """Run all non-skipped checks in the spec §5.5 order."""
    checks: list[StatusCheck] = []

    cfg_checks = config_sanity.run()
    checks.extend(cfg_checks)

    # Step-1 early-abort on fatal STA001 applies to text mode; caller decides.
    if any(c.rule == "STA001" for c in cfg_checks) and args._early_abort:
        return checks

    checks.extend(db_freshness.run())
    if not args.skip_toolchain:
        checks.extend(toolchain.run())
    if not args.skip_lint:
        checks.extend(lint_summary.run())
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate health report for a ForgeDS project.",
        epilog="Exit codes: 0=ok, 1=warn, 2=fail",
    )
    parser.add_argument("--format", dest="format", default=None, choices=["text", "json-v1"],
                        help="Output format (default: text; FORGEDS_OUTPUT env also honored).")
    parser.add_argument("--skip-lint", action="store_true",
                        help="Omit the lint_summary check (useful in CI where lint ran separately).")
    parser.add_argument("--skip-toolchain", action="store_true",
                        help="Omit the toolchain check.")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Text mode: suppress OK rows. JSON mode: ignored.")
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Text mode aborts early on broken YAML (STA001); JSON mode runs everything.
    args._early_abort = (fmt == "text")

    checks = _run_all_checks(args)

    if fmt == "json-v1":
        print(render_json(checks))
    else:
        if args.quiet:
            filtered = [c for c in checks if c.status != "ok"]
            # keep at least one check per section if possible, but quiet mode is cosmetic
            checks_to_render = filtered or checks
        else:
            checks_to_render = checks
        print(render_text(checks_to_render))

    return exit_code(checks)


if __name__ == "__main__":
    sys.exit(main())
