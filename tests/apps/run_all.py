#!/usr/bin/env python3
"""Validate all Zia-exported .ds files in the test corpus.

Runs forgeds-validate-ds against each app's zia_export.ds.
Exit 0 if all pass clean, exit 1 if any produce errors or warnings.
"""

import subprocess
import sys
from pathlib import Path

APPS_DIR = Path(__file__).parent
apps = sorted(p.parent.name for p in APPS_DIR.rglob("zia_export.ds"))

if not apps:
    print("No zia_export.ds files found in tests/apps/")
    sys.exit(1)

total = 0
failed = 0

for app in apps:
    ds_path = APPS_DIR / app / "zia_export.ds"
    total += 1
    result = subprocess.run(
        [sys.executable, "-m", "forgeds.core.validate_ds", str(ds_path)],
        capture_output=True, text=True,
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    if result.returncode != 0:
        failed += 1
    print(f"  [{status}] {app}")
    if result.returncode != 0:
        for line in result.stdout.splitlines():
            if line.strip() and not line.startswith("---"):
                print(f"         {line}")
        for line in result.stderr.splitlines():
            if line.strip():
                print(f"         {line}")

print(f"\n{total} apps tested: {total - failed} passed, {failed} failed")
sys.exit(1 if failed else 0)
