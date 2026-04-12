"""CLI entry point for running Deluge scripts locally.

Usage:
    python -m forgeds.runtime script.dg
    python -m forgeds.runtime script.dg --input '{"Name": "Test", "Amount": 100}'
    python -m forgeds.runtime script.dg --quiet
"""

from __future__ import annotations

import argparse
import json
import sys

from forgeds._shared.diagnostics import format_diagnostic
from forgeds.runtime.interpreter import Interpreter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Deluge script locally with stubbed side effects",
        epilog="Exit codes: 0=success, 1=runtime errors, 2=parse errors",
    )
    parser.add_argument("script", help="Path to .dg script file")
    parser.add_argument(
        "--input", "-i", default="{}",
        help='JSON object for input.* fields (default: {})',
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Only show errors and side effects, suppress info/variables",
    )
    args = parser.parse_args()

    try:
        with open(args.script, encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Cannot read file: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        input_data = json.loads(args.input)
    except json.JSONDecodeError as e:
        print(f"Invalid --input JSON: {e}", file=sys.stderr)
        sys.exit(2)

    result = Interpreter.run_source(source, input_data=input_data,
                                    filename=args.script)

    # Errors
    if result.errors:
        use_color = sys.stderr.isatty()
        for i, diag in enumerate(result.errors, 1):
            print(format_diagnostic(diag, i, use_color=use_color),
                  file=sys.stderr)

    # Info log
    if not args.quiet and result.info_log:
        print("--- Info Log ---")
        for msg in result.info_log:
            print(f"  {msg}")

    # Alert log
    if result.alert_log:
        print("--- Alerts ---")
        for msg in result.alert_log:
            print(f"  {msg}")

    # Side effects
    if result.side_effects.all():
        print(result.side_effects.summary())

    # Cancel submit
    if result.cancelled:
        print("--- Form submission CANCELLED ---")

    # Return value
    if result.return_value is not None:
        print(f"Return: {result.return_value}")

    # Variables
    if not args.quiet:
        vars_to_show = {
            k: v for k, v in result.variables.items()
            if not k.startswith("_") and k != "input"
        }
        if vars_to_show:
            print("--- Variables ---")
            for k, v in sorted(vars_to_show.items()):
                print(f"  {k} = {v!r}")

    sys.exit(1 if result.errors else 0)


if __name__ == "__main__":
    main()
