"""Resolve CLI `--format` against `FORGEDS_OUTPUT` env var."""

from __future__ import annotations

import os
from typing import Literal

Format = Literal["text", "json-v1"]
_VALID = ("text", "json-v1")


class UnknownFormatError(ValueError):
    """Raised when an unknown format value is supplied via CLI or env."""

    def __init__(self, value: str, source: str) -> None:
        super().__init__(
            f"forgeds: unknown output format {value!r} "
            f"(expected: {', '.join(_VALID)}) [source: {source}]"
        )
        self.value = value
        self.source = source


def resolve_format(cli_flag: str | None) -> Format:
    """CLI flag wins over env; env wins over default 'text'."""
    if cli_flag is not None:
        if cli_flag not in _VALID:
            raise UnknownFormatError(cli_flag, "CLI flag --format")
        return cli_flag  # type: ignore[return-value]
    env = os.environ.get("FORGEDS_OUTPUT")
    if env:
        if env not in _VALID:
            raise UnknownFormatError(env, "FORGEDS_OUTPUT")
        return env  # type: ignore[return-value]
    return "text"
