"""Variable scopes and zoho.* system variable stubs for the local interpreter.

The Environment manages nested variable scopes (global -> function -> block)
and provides zoho.* system variables with sensible test defaults.

Usage:
    env = Environment()
    env.define("x", 42)
    env.get("x")  # 42

    env.push_scope()
    env.define("y", "hello")
    env.pop_scope()
    # y is now out of scope
"""

from __future__ import annotations

from datetime import datetime, date, time
from typing import Any


class Environment:
    """Lexically scoped variable environment with zoho.* stubs."""

    def __init__(self, input_data: dict[str, Any] | None = None) -> None:
        # Scope stack: each scope is a dict[str, Any]
        # Index 0 is the global scope
        self._scopes: list[dict[str, Any]] = [{}]

        # Set up input.* fields
        self._input = input_data or {}

        # Set up zoho.* system variables
        now = datetime.now()
        self._zoho: dict[str, Any] = {
            "zoho.currentdate": now.strftime("%Y-%m-%d"),
            "zoho.currenttime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "zoho.loginuser": "test@example.com",
            "zoho.loginuserid": "test@example.com",
            "zoho.loginuser.name": "Test User",
            "zoho.adminuser": "admin@example.com",
            "zoho.adminuserid": "admin@example.com",
            "zoho.appname": "ForgeDS-Test",
            "zoho.appuri": "/app/forgeds-test",
            "zoho.ipaddress": "127.0.0.1",
            "zoho.device.type": "desktop",
        }

    # ----------------------------------------------------------
    # Scope management
    # ----------------------------------------------------------

    def push_scope(self) -> None:
        """Enter a new nested scope (block, loop, etc.)."""
        self._scopes.append({})

    def pop_scope(self) -> None:
        """Exit the current scope. Raises if at global scope."""
        if len(self._scopes) <= 1:
            raise RuntimeError("Cannot pop global scope")
        self._scopes.pop()

    # ----------------------------------------------------------
    # Variable access
    # ----------------------------------------------------------

    def define(self, name: str, value: Any) -> None:
        """Define or update a variable in the current scope."""
        self._scopes[-1][name] = value

    def set(self, name: str, value: Any) -> None:
        """Set a variable, searching from innermost to outermost scope.

        If the variable doesn't exist in any scope, define it in the
        current (innermost) scope.
        """
        for scope in reversed(self._scopes):
            if name in scope:
                scope[name] = value
                return
        # Not found — define in current scope
        self._scopes[-1][name] = value

    def get(self, name: str) -> Any:
        """Look up a variable from innermost to outermost scope."""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"Undefined variable: {name}")

    def has(self, name: str) -> bool:
        """Check if a variable is defined in any scope."""
        return any(name in scope for scope in self._scopes)

    # ----------------------------------------------------------
    # Special accessors
    # ----------------------------------------------------------

    def get_input(self, field_name: str) -> Any:
        """Access input.FieldName values."""
        if field_name in self._input:
            return self._input[field_name]
        return None

    def set_input(self, field_name: str, value: Any) -> None:
        """Set an input.FieldName value."""
        self._input[field_name] = value

    def get_zoho(self, path: str) -> Any:
        """Access zoho.* system variables."""
        if path in self._zoho:
            return self._zoho[path]
        return None

    def set_zoho(self, path: str, value: Any) -> None:
        """Override a zoho.* variable for testing."""
        self._zoho[path] = value

    # ----------------------------------------------------------
    # Debugging
    # ----------------------------------------------------------

    def dump(self) -> dict[str, Any]:
        """Return all variables across all scopes (innermost wins)."""
        merged: dict[str, Any] = {}
        for scope in self._scopes:
            merged.update(scope)
        return merged
