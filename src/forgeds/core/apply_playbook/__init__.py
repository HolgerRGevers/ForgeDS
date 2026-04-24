"""forgeds-apply-playbook — mutate a .ds to encode playbook-declared workflows.

See docs/superpowers/specs/2026-04-24-forgeds-apply-playbook-design.md.
"""
from __future__ import annotations


def apply_playbook(ds_path: str, playbook_path: str, out_path: str, **kwargs) -> int:
    """Library entry. Stub — implementation lands in Task 9 (orchestrator)."""
    raise NotImplementedError("forgeds-apply-playbook: orchestrator not yet implemented (Task 9)")


__all__ = ["apply_playbook"]
