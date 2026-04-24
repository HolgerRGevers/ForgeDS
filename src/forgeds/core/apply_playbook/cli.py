"""CLI entry-point for forgeds-apply-playbook."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forgeds-apply-playbook",
        description="Mutate a .ds to encode playbook-declared workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for sub_name in ("apply", "validate", "preview"):
        sub = subparsers.add_parser(sub_name, help=f"{sub_name} subcommand (stub)")
        sub.add_argument("--ds", required=True, help="Source .ds file")
        sub.add_argument("--playbook", required=True, help="Playbook MD file")
        if sub_name == "apply":
            sub.add_argument("--out", required=True, help="Destination .ds path")
            sub.add_argument("--force", action="store_true")
            sub.add_argument(
                "--custom-action-workflow-mode",
                default="stub-unwired",
                choices=["form", "standalone", "stub-unwired"],
            )
            sub.add_argument("--dry-run", action="store_true")
        sub.add_argument("--ir-dump", help="Write parsed IR as JSON to this path")
        sub.add_argument("--json", action="store_true", help="Emit JSON envelope to stdout")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Stub: full orchestration lands in Task 9 + 10. For now, print and exit 0.
    print(f"forgeds-apply-playbook {args.command}: stub (not yet implemented)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
