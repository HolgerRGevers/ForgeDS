"""Side-effect stubs for the local Deluge interpreter.

Real Deluge actions (sendmail, insert into, invokeUrl, etc.) become
logged stubs when running locally. The SideEffectLog captures every
action for assertion in tests.

Usage:
    log = SideEffectLog()
    log.record("sendmail", {"to": "a@b.com", "subject": "Hi"})
    assert log.calls("sendmail") == 1
    assert log.last("sendmail")["to"] == "a@b.com"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SideEffect:
    """A single recorded side effect."""
    action: str           # "sendmail", "insert", "invokeUrl", "sendsms", "alert", "info", "openUrl"
    params: dict[str, Any]
    result: Any = None    # For insert (returns row ID) or invokeUrl (returns response)


class SideEffectLog:
    """Collects all side effects during script execution."""

    def __init__(self) -> None:
        self._log: list[SideEffect] = []
        self._next_id = 1000  # Auto-increment for insert stubs

    def record(self, action: str, params: dict[str, Any], result: Any = None) -> Any:
        """Record a side effect and return a stub result."""
        if result is None:
            result = self._default_result(action)
        self._log.append(SideEffect(action=action, params=dict(params), result=result))
        return result

    def _default_result(self, action: str) -> Any:
        if action == "insert":
            row_id = self._next_id
            self._next_id += 1
            return row_id
        if action == "invokeUrl":
            return '{"status": "ok"}'
        if action == "delete":
            return True
        return None

    # ----------------------------------------------------------
    # Query helpers for assertions
    # ----------------------------------------------------------

    def all(self) -> list[SideEffect]:
        """Return all recorded side effects."""
        return list(self._log)

    def by_action(self, action: str) -> list[SideEffect]:
        """Return all side effects of a given action type."""
        return [e for e in self._log if e.action == action]

    def calls(self, action: str) -> int:
        """Count how many times an action was called."""
        return sum(1 for e in self._log if e.action == action)

    def last(self, action: str) -> dict[str, Any] | None:
        """Return params of the last call of a given action type."""
        matches = self.by_action(action)
        return matches[-1].params if matches else None

    def clear(self) -> None:
        """Clear all recorded side effects."""
        self._log.clear()

    def summary(self) -> str:
        """Human-readable summary of all side effects."""
        if not self._log:
            return "No side effects recorded."
        lines = [f"Side effects ({len(self._log)} total):"]
        for i, e in enumerate(self._log, 1):
            param_str = ", ".join(f"{k}={v!r}" for k, v in e.params.items())
            lines.append(f"  {i}. {e.action}({param_str})")
            if e.result is not None:
                lines.append(f"     -> {e.result!r}")
        return "\n".join(lines)


# ============================================================
# Built-in function stubs
# ============================================================

class BuiltinFunctions:
    """Stub implementations of common Deluge built-in functions."""

    @staticmethod
    def ifnull(value: Any, fallback: Any) -> Any:
        return fallback if value is None else value

    @staticmethod
    def isnull(value: Any) -> bool:
        return value is None

    @staticmethod
    def toNumber(value: Any) -> int | float:
        if value is None:
            return 0
        try:
            s = str(value)
            return int(s) if "." not in s else float(s)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def toString(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def length(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, (str, list, dict)):
            return len(value)
        return 0

    @staticmethod
    def trim(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    @staticmethod
    def startsWith(value: Any, prefix: Any) -> bool:
        return str(value).startswith(str(prefix)) if value is not None else False

    @staticmethod
    def endsWith(value: Any, suffix: Any) -> bool:
        return str(value).endswith(str(suffix)) if value is not None else False

    @staticmethod
    def contains(value: Any, substring: Any) -> bool:
        return str(substring) in str(value) if value is not None else False

    @staticmethod
    def getSuffix(value: Any, delimiter: Any) -> str:
        s = str(value) if value is not None else ""
        d = str(delimiter)
        idx = s.rfind(d)
        return s[idx + len(d):] if idx >= 0 else s

    @staticmethod
    def getPrefix(value: Any, delimiter: Any) -> str:
        s = str(value) if value is not None else ""
        d = str(delimiter)
        idx = s.find(d)
        return s[:idx] if idx >= 0 else s

    @staticmethod
    def replaceAll(value: Any, old: Any, new: Any) -> str:
        return str(value).replace(str(old), str(new)) if value is not None else ""

    @staticmethod
    def toUpperCase(value: Any) -> str:
        return str(value).upper() if value is not None else ""

    @staticmethod
    def toLowerCase(value: Any) -> str:
        return str(value).lower() if value is not None else ""

    @staticmethod
    def daysBetween(d1: Any, d2: Any) -> int:
        """Stub: returns 0. Real implementation would parse dates."""
        return 0

    @staticmethod
    def hoursBetween(d1: Any, d2: Any) -> int:
        """Stub: returns 0."""
        return 0

    @staticmethod
    def size(value: Any) -> int:
        """Collection size (same as length for lists/maps)."""
        if value is None:
            return 0
        if isinstance(value, (list, dict)):
            return len(value)
        return 0

    @staticmethod
    def count(value: Any) -> int:
        """Query result count."""
        if value is None:
            return 0
        if isinstance(value, list):
            return len(value)
        return 1


# Registry of standalone built-in functions
BUILTIN_FUNCTIONS: dict[str, Any] = {
    "ifnull": BuiltinFunctions.ifnull,
    "isnull": BuiltinFunctions.isnull,
    "toNumber": BuiltinFunctions.toNumber,
    "toString": BuiltinFunctions.toString,
    "length": BuiltinFunctions.length,
    "trim": BuiltinFunctions.trim,
    "startsWith": BuiltinFunctions.startsWith,
    "endsWith": BuiltinFunctions.endsWith,
    "contains": BuiltinFunctions.contains,
    "getSuffix": BuiltinFunctions.getSuffix,
    "getPrefix": BuiltinFunctions.getPrefix,
    "replaceAll": BuiltinFunctions.replaceAll,
    "toUpperCase": BuiltinFunctions.toUpperCase,
    "toLowerCase": BuiltinFunctions.toLowerCase,
    "daysBetween": BuiltinFunctions.daysBetween,
    "hoursBetween": BuiltinFunctions.hoursBetween,
    "size": BuiltinFunctions.size,
    "count": BuiltinFunctions.count,
}

# Method stubs — called as obj.method(args)
METHOD_STUBS: dict[str, Any] = {
    "get": lambda obj, key: obj.get(key) if isinstance(obj, dict) else None,
    "put": lambda obj, key, val: obj.__setitem__(key, val) if isinstance(obj, dict) else None,
    "remove": lambda obj, key: obj.pop(key, None) if isinstance(obj, dict) else (obj.remove(key) if isinstance(obj, list) else None),
    "add": lambda obj, val: obj.append(val) if isinstance(obj, list) else None,
    "addAll": lambda obj, vals: obj.extend(vals) if isinstance(obj, list) else None,
    "clear": lambda obj: obj.clear() if isinstance(obj, (list, dict)) else None,
    "isEmpty": lambda obj: len(obj) == 0 if isinstance(obj, (list, dict, str)) else True,
    "toString": lambda obj: str(obj),
    "toLong": lambda obj: int(obj) if obj is not None else 0,
    "toMap": lambda obj: dict(obj) if isinstance(obj, dict) else {},
    "toList": lambda obj: list(obj) if isinstance(obj, (list, dict)) else [],
    "trim": lambda obj: str(obj).strip(),
    "length": lambda obj: len(obj) if isinstance(obj, (str, list, dict)) else 0,
    "count": lambda obj: len(obj) if isinstance(obj, list) else (1 if obj is not None else 0),
    "startsWith": lambda obj, s: str(obj).startswith(str(s)),
    "endsWith": lambda obj, s: str(obj).endswith(str(s)),
    "contains": lambda obj, s: str(s) in str(obj) if isinstance(obj, str) else (s in obj if isinstance(obj, (list, dict)) else False),
    "toUpperCase": lambda obj: str(obj).upper(),
    "toLowerCase": lambda obj: str(obj).lower(),
    "replaceAll": lambda obj, old, new: str(obj).replace(str(old), str(new)),
    "getSuffix": lambda obj, d: str(obj)[str(obj).rfind(str(d)) + len(str(d)):] if str(d) in str(obj) else str(obj),
    "getPrefix": lambda obj, d: str(obj)[:str(obj).find(str(d))] if str(d) in str(obj) else str(obj),
    "insert": lambda obj, row: obj.append(row) if isinstance(obj, list) else None,
}
