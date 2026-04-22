# Hybrid-IDE Backend Gap Close Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace four mock bridge handlers (handle_ai_chat, handle_inspect_element, handle_build_project, handle_refine_prompt) with real implementations backed by the Claude API and existing ForgeDS Python tooling.

**Architecture:** Bridge backend Python only. New modules in bridge/ for credentials, effort levels, prompts, session state, cancellation, relationship graph, and build pipeline. Existing forgeds.lang/ (AST) and forgeds.core/ (scaffold/build/lint) invoked as libraries. One cross-cutting TypeScript change: bridge.ts type union expansion.

**Tech Stack:** Python 3.10+, anthropic>=0.39.0 (async), pyyaml>=6.0, pytest + pytest-asyncio, existing ForgeDS modules.

**Reference spec:** docs/superpowers/specs/2026-04-22-hybrid-ide-backend-gap-close.md

**Working directory for all tasks:** `C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS`

---

## File plan

### New files
| File | Responsibility |
|------|---------------|
| `bridge/claude_config.py` | Credential resolution, EFFORT_LEVELS table, async Anthropic client factory, error-response helpers |
| `bridge/cancellation.py` | `active_streams` registry + register/cancel/is_cancelled helpers for streaming handlers |
| `bridge/session_store.py` | In-memory chat session store with idle-eviction GC task |
| `bridge/prompts.py` | System-prompt builders: ai_chat + refine_prompt, CLAUDE.md digest constant |
| `bridge/relationship_builder.py` | Graph dataclasses + AST walker + edge/usage extraction + build entry point |
| `bridge/build_pipeline.py` | GenerationPlan dataclass, scaffold + fill pipelines, active-scaffolds registry |
| `bridge/graph_store.py` | Per-session `RelationshipGraph` cache used by `handle_inspect_element` |
| `bridge/tests/__init__.py` | Makes bridge/tests a package |
| `bridge/tests/conftest.py` | Registers pytest-asyncio |
| `bridge/tests/test_claude_config.py` | Unit tests for credentials, effort map, error-response helpers |
| `bridge/tests/test_cancellation.py` | Unit tests for cancellation registry |
| `bridge/tests/test_session_store.py` | Unit tests for session state + GC |
| `bridge/tests/test_prompts.py` | Unit tests for prompt builders |
| `bridge/tests/test_handle_ai_chat.py` | Handler tests with mocked Anthropic client |
| `bridge/tests/test_refine_prompt.py` | Handler + JSON-extraction tests with mocked client |
| `bridge/tests/test_relationship_builder.py` | Graph construction tests against fixture .ds |
| `bridge/tests/test_handle_inspect_element.py` | Handler tests against built graph |
| `bridge/tests/test_build_pipeline.py` | Plan extraction, scaffold, fill tests |
| `bridge/tests/test_handle_build_project.py` | Handler tests for scaffold + fill modes |
| `bridge/tests/test_graph_store.py` | Unit tests for graph cache |
| `bridge/tests/test_bridge_ts_types.py` | Guards the bridge.ts type-union expansion |
| `bridge/tests/test_environment.py` | Phase-0 smoke (deps, template, gitignore) |
| `bridge/tests/test_server_cancel_routing.py` | Cancel-message routing in server.py |
| `bridge/tests/fixtures/tiny_app.ds` | Small fixture .ds with 2 forms + 2 workflows for graph tests |
| `bridge/tests/live_api/__init__.py` | Package marker for gated live tests |
| `bridge/tests/live_api/test_live_smoke.py` | Live-API smoke tests gated by `ANTHROPIC_API_KEY` |
| `templates/anthropic.yaml.template` | Template file users copy to `~/.forgeds/anthropic.yaml` |

### Modified files
| File | Change |
|------|--------|
| `bridge/requirements.txt` | Add `anthropic>=0.39.0`, `pyyaml>=6.0`, `pytest>=7`, `pytest-asyncio>=0.21` |
| `bridge/handlers.py` | Replace 4 mock handlers (ai_chat, refine_prompt, inspect_element, build_project) |
| `bridge/server.py` | Route `{cancel: true, id}` messages, stream ai_chat chunks |
| `web/src/types/bridge.ts` | Expand `BridgeMessage` type union to include all 14 handler types |
| `.gitignore` | Add `config/anthropic.yaml` (defence-in-depth; canonical path is `~/.forgeds/`) |

---

## Phase 0 — Environment

### Task 0.1: Dependencies, template, .gitignore

**Files:**
- Modify: `bridge/requirements.txt`
- Create: `templates/anthropic.yaml.template`
- Modify: `.gitignore`
- Create: `bridge/tests/__init__.py`
- Create: `bridge/tests/test_environment.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/__init__.py` (empty). Then create `bridge/tests/test_environment.py`:

```python
"""Smoke tests for Phase 0 environment scaffolding."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_requirements_lists_anthropic_and_pyyaml():
    text = (REPO_ROOT / "bridge" / "requirements.txt").read_text(encoding="utf-8")
    assert "anthropic>=0.39.0" in text
    assert "pyyaml>=6.0" in text
    assert "pytest-asyncio" in text


def test_anthropic_template_exists():
    tpl = REPO_ROOT / "templates" / "anthropic.yaml.template"
    assert tpl.exists(), "templates/anthropic.yaml.template must exist"
    assert "api_key:" in tpl.read_text(encoding="utf-8")


def test_gitignore_blocks_project_anthropic_yaml():
    gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "config/anthropic.yaml" in gi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_environment.py -v`
Expected: FAIL — all 3 asserts fail because the strings are not yet present.

- [ ] **Step 3: Implement**

Rewrite `bridge/requirements.txt`:

```text
websockets>=12.0
anthropic>=0.39.0
pyyaml>=6.0
pytest>=7.0
pytest-asyncio>=0.21
```

Create `templates/anthropic.yaml.template`:

```yaml
# ForgeDS - Anthropic API credentials
# Copy to ~/.forgeds/anthropic.yaml and fill in your key.
# Alternatively, set the ANTHROPIC_API_KEY environment variable.
api_key: YOUR_ANTHROPIC_API_KEY_HERE
```

Append to `.gitignore` (defence-in-depth — real file lives in `~/.forgeds/anthropic.yaml`):

```text

# Anthropic credentials (defence-in-depth; canonical path is ~/.forgeds/anthropic.yaml)
config/anthropic.yaml
```

Then install deps locally: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pip install -r bridge/requirements.txt`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_environment.py -v`
Expected: PASS — 3/3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/requirements.txt templates/anthropic.yaml.template .gitignore bridge/tests/__init__.py bridge/tests/test_environment.py
git commit -m "chore(bridge): add anthropic+pyyaml deps, credentials template, gitignore defence"
```

---

## Phase 1 — Shared infrastructure

### Task 1.1: Credentials resolution

**Files:**
- Create: `bridge/claude_config.py`
- Create: `bridge/tests/test_claude_config.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_claude_config.py`:

```python
import os
from pathlib import Path

import pytest

from bridge.claude_config import resolve_api_key


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    assert resolve_api_key() == "sk-ant-from-env"


def test_resolve_api_key_from_yaml(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_home = tmp_path / "home"
    (fake_home / ".forgeds").mkdir(parents=True)
    (fake_home / ".forgeds" / "anthropic.yaml").write_text(
        "api_key: sk-ant-from-yaml\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    assert resolve_api_key() == "sk-ant-from-yaml"


def test_resolve_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert resolve_api_key() is None


def test_resolve_api_key_env_wins_over_yaml(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-wins")
    fake_home = tmp_path / "home"
    (fake_home / ".forgeds").mkdir(parents=True)
    (fake_home / ".forgeds" / "anthropic.yaml").write_text(
        "api_key: sk-ant-yaml-loser\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    assert resolve_api_key() == "sk-ant-env-wins"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.claude_config'`.

- [ ] **Step 3: Implement**

Create `bridge/claude_config.py`:

```python
"""Anthropic credentials, effort-level mapping, client factory, error helpers."""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def resolve_api_key() -> str | None:
    """Return the Anthropic API key, preferring env over ~/.forgeds/anthropic.yaml."""
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env and env.strip():
        return env.strip()
    yaml_path = Path.home() / ".forgeds" / "anthropic.yaml"
    if yaml_path.exists():
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            key = data.get("api_key")
            if isinstance(key, str) and key.strip() and key.strip() != "YOUR_ANTHROPIC_API_KEY_HERE":
                return key.strip()
        except yaml.YAMLError:
            return None
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: PASS — 4/4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/claude_config.py bridge/tests/test_claude_config.py
git commit -m "feat(bridge): resolve Anthropic API key from env or ~/.forgeds/anthropic.yaml"
```

---

### Task 1.2: EFFORT_LEVELS table + client factory

**Files:**
- Modify: `bridge/claude_config.py`
- Modify: `bridge/tests/test_claude_config.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_claude_config.py`:

```python
from bridge.claude_config import (
    EFFORT_LEVELS,
    DEFAULT_IDE_EFFORT,
    DEFAULT_APP_CREATION_EFFORT,
    get_effort_config,
    build_anthropic_client,
)


def test_effort_levels_has_all_four_tiers():
    assert set(EFFORT_LEVELS.keys()) == {"low", "medium", "high", "max"}
    for tier, cfg in EFFORT_LEVELS.items():
        assert "model" in cfg
        assert "max_tokens" in cfg
        assert "thinking" in cfg


def test_default_efforts():
    assert DEFAULT_IDE_EFFORT == "high"
    assert DEFAULT_APP_CREATION_EFFORT == "max"


def test_get_effort_config_unknown_falls_back_to_high():
    cfg = get_effort_config("bogus")
    assert cfg == EFFORT_LEVELS["high"]


def test_get_effort_config_none_uses_default_ide():
    cfg = get_effort_config(None)
    assert cfg == EFFORT_LEVELS[DEFAULT_IDE_EFFORT]


def test_build_anthropic_client_returns_none_when_no_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert build_anthropic_client() is None


def test_build_anthropic_client_returns_client_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = build_anthropic_client()
    assert client is not None
    assert client.__class__.__name__ == "AsyncAnthropic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'EFFORT_LEVELS' from 'bridge.claude_config'`.

- [ ] **Step 3: Implement**

Append to `bridge/claude_config.py`:

```python
# ---------------------------------------------------------------------------
# Effort-level mapping - single source of truth
# ---------------------------------------------------------------------------
EFFORT_LEVELS: dict[str, dict] = {
    "low":    {"model": "claude-haiku-4-5-20251001", "thinking": None,  "max_tokens": 2048},
    "medium": {"model": "claude-haiku-4-5-20251001", "thinking": 4096,  "max_tokens": 4096},
    "high":   {"model": "claude-sonnet-4-6",         "thinking": None,  "max_tokens": 4096},
    "max":    {"model": "claude-opus-4-7",           "thinking": 16384, "max_tokens": 8192},
}
DEFAULT_IDE_EFFORT = "high"
DEFAULT_APP_CREATION_EFFORT = "max"


def get_effort_config(effort: str | None) -> dict:
    """Return the effort config for *effort*, falling back to DEFAULT_IDE_EFFORT."""
    if effort is None:
        return EFFORT_LEVELS[DEFAULT_IDE_EFFORT]
    return EFFORT_LEVELS.get(effort, EFFORT_LEVELS[DEFAULT_IDE_EFFORT])


def build_anthropic_client():
    """Return an AsyncAnthropic client, or None if no API key is configured."""
    key = resolve_api_key()
    if not key:
        return None
    from anthropic import AsyncAnthropic  # deferred import so tests without SDK still parse
    return AsyncAnthropic(api_key=key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: PASS — 10/10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/claude_config.py bridge/tests/test_claude_config.py
git commit -m "feat(bridge): add EFFORT_LEVELS mapping and AsyncAnthropic client factory"
```

---

### Task 1.3: Error-response helpers

**Files:**
- Modify: `bridge/claude_config.py`
- Modify: `bridge/tests/test_claude_config.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_claude_config.py`:

```python
from bridge.claude_config import build_error, ERROR_CODES, no_api_key_error


def test_build_error_minimal():
    err = build_error("Missing field", "invalid_request")
    assert err == {"error": "Missing field", "code": "invalid_request"}


def test_build_error_with_details():
    err = build_error("Not found", "not_found", details={"id": "x"})
    assert err["details"] == {"id": "x"}
    assert err["code"] == "not_found"


def test_error_codes_enumerated():
    expected = {
        "no_api_key", "rate_limited", "upstream_error", "parse_error",
        "invalid_request", "not_found", "timeout", "cancelled",
    }
    assert expected.issubset(set(ERROR_CODES))


def test_build_error_rejects_unknown_code():
    with pytest.raises(ValueError):
        build_error("x", "bogus_code")


def test_no_api_key_error_has_setup_hint():
    err = no_api_key_error()
    assert err["code"] == "no_api_key"
    assert "setup_hint" in err["details"]
    assert "ANTHROPIC_API_KEY" in err["details"]["setup_hint"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_error'`.

- [ ] **Step 3: Implement**

Append to `bridge/claude_config.py`:

```python
# ---------------------------------------------------------------------------
# Standard error codes + response builder
# ---------------------------------------------------------------------------
ERROR_CODES: set[str] = {
    "no_api_key",
    "rate_limited",
    "upstream_error",
    "parse_error",
    "invalid_request",
    "not_found",
    "timeout",
    "cancelled",
}


def build_error(message: str, code: str, *, details: dict | None = None) -> dict:
    """Construct a standard error response dict.

    Raises ValueError if *code* is not in ERROR_CODES.
    """
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code!r}; must be one of {sorted(ERROR_CODES)}")
    out: dict = {"error": message, "code": code}
    if details is not None:
        out["details"] = details
    return out


NO_API_KEY_HINT = (
    "Set ANTHROPIC_API_KEY or create ~/.forgeds/anthropic.yaml "
    "(see templates/anthropic.yaml.template)"
)


def no_api_key_error() -> dict:
    """Return the canonical 'no API key' error response."""
    return build_error(
        "Anthropic API key not configured.",
        "no_api_key",
        details={"setup_hint": NO_API_KEY_HINT},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_claude_config.py -v`
Expected: PASS — 15/15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/claude_config.py bridge/tests/test_claude_config.py
git commit -m "feat(bridge): add standard error codes + build_error/no_api_key_error helpers"
```

---

### Task 1.4: Cancellation registry

**Files:**
- Create: `bridge/cancellation.py`
- Create: `bridge/tests/conftest.py`
- Create: `bridge/tests/test_cancellation.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/conftest.py`:

```python
"""Shared pytest config for bridge tests. Enables pytest-asyncio."""
import pytest_asyncio  # noqa: F401 -- imported to register the plugin
```

Create `bridge/tests/test_cancellation.py`:

```python
import asyncio

import pytest

from bridge.cancellation import register_stream, cancel_stream, is_cancelled, unregister_stream


@pytest.mark.asyncio
async def test_register_then_is_cancelled_false():
    event = register_stream("msg_1")
    assert not event.is_set()
    assert not is_cancelled("msg_1")
    unregister_stream("msg_1")


@pytest.mark.asyncio
async def test_cancel_sets_event():
    register_stream("msg_2")
    assert cancel_stream("msg_2") is True
    assert is_cancelled("msg_2")
    unregister_stream("msg_2")


@pytest.mark.asyncio
async def test_cancel_unknown_id_returns_false():
    assert cancel_stream("never_registered") is False


@pytest.mark.asyncio
async def test_is_cancelled_unknown_id_false():
    assert is_cancelled("never_registered") is False


@pytest.mark.asyncio
async def test_unregister_removes_event():
    register_stream("msg_3")
    unregister_stream("msg_3")
    assert not is_cancelled("msg_3")
    # cancel after unregister is a no-op
    assert cancel_stream("msg_3") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_cancellation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.cancellation'`.

- [ ] **Step 3: Implement**

Create `bridge/cancellation.py`:

```python
"""Registry of in-flight streaming requests, with per-request asyncio.Event."""
from __future__ import annotations

import asyncio

# Module-level registry: message_id -> Event.
# Set the event to signal cancellation; handlers poll between chunks.
active_streams: dict[str, asyncio.Event] = {}


def register_stream(message_id: str) -> asyncio.Event:
    """Create and register a cancellation Event for *message_id*.

    If an event already exists for the id (rare, same-id retry), return it.
    """
    event = active_streams.get(message_id)
    if event is None:
        event = asyncio.Event()
        active_streams[message_id] = event
    return event


def cancel_stream(message_id: str) -> bool:
    """Set the Event for *message_id*, returning True if the id was known."""
    event = active_streams.get(message_id)
    if event is None:
        return False
    event.set()
    return True


def is_cancelled(message_id: str) -> bool:
    """Return True if *message_id* has been cancelled."""
    event = active_streams.get(message_id)
    return bool(event and event.is_set())


def unregister_stream(message_id: str) -> None:
    """Remove the Event for *message_id* (call from the handler's finally block)."""
    active_streams.pop(message_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_cancellation.py -v`
Expected: PASS — 5/5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/cancellation.py bridge/tests/test_cancellation.py bridge/tests/conftest.py
git commit -m "feat(bridge): add per-request cancellation registry for streaming handlers"
```

---

### Task 1.5: bridge.ts type-union expansion

**Files:**
- Modify: `web/src/types/bridge.ts`
- Create: `bridge/tests/test_bridge_ts_types.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_bridge_ts_types.py`:

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bridge_ts_has_full_message_type_union():
    content = (REPO_ROOT / "web" / "src" / "types" / "bridge.ts").read_text(encoding="utf-8")
    required_members = [
        "refine_prompt", "build_project", "lint_check", "get_status",
        "parse_ds", "read_file", "inspect_element", "ai_chat",
        "get_schema", "run_validation", "mock_upload",
        "generate_api_code", "get_api_list", "export_api",
    ]
    for m in required_members:
        assert f'"{m}"' in content, f"bridge.ts missing member {m!r}"
    assert "BridgeMessageType" in content, "expected BridgeMessageType type alias"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_bridge_ts_types.py -v`
Expected: FAIL — missing `parse_ds`, `read_file`, `inspect_element`, etc.

- [ ] **Step 3: Implement**

Rewrite `web/src/types/bridge.ts`:

```typescript
/** Connection state of the bridge WebSocket client. */
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/** All message types dispatched by the bridge client. */
export type BridgeMessageType =
  | "refine_prompt"
  | "build_project"
  | "lint_check"
  | "get_status"
  | "parse_ds"
  | "read_file"
  | "inspect_element"
  | "ai_chat"
  | "get_schema"
  | "run_validation"
  | "mock_upload"
  | "generate_api_code"
  | "get_api_list"
  | "export_api";

/** Outbound message sent to the bridge server. */
export interface BridgeMessage {
  id: string;
  type: BridgeMessageType;
  data: Record<string, unknown>;
}

/** Inbound message received from the bridge server. */
export interface BridgeResponse {
  id: string;
  type: "response" | "stream" | "stream_end" | "error";
  data: Record<string, unknown>;
}

/** Zustand store shape for the bridge client. */
export interface BridgeStore {
  status: ConnectionStatus;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  send: (
    type: BridgeMessageType,
    data: Record<string, unknown>,
  ) => Promise<Record<string, unknown>>;
  sendStream: (
    type: BridgeMessageType,
    data: Record<string, unknown>,
    onChunk: (chunk: Record<string, unknown>) => void,
  ) => Promise<Record<string, unknown>>;
}

/** Listener callback for connection-state changes. */
export type ConnectionListener = (status: ConnectionStatus) => void;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_bridge_ts_types.py -v`
Expected: PASS — 1/1 test passes.

Also verify frontend still type-checks: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS/web && npm run typecheck`
Expected: no new errors introduced by the type-union change.

- [ ] **Step 5: Commit**

```bash
git add web/src/types/bridge.ts bridge/tests/test_bridge_ts_types.py
git commit -m "fix(web): expand BridgeMessage type union to all 14 handler types"
```

---

### Task 1.6: Server cancellation routing

**Files:**
- Modify: `bridge/server.py`
- Create: `bridge/tests/test_server_cancel_routing.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_server_cancel_routing.py`:

```python
"""Verify that an incoming {cancel: true, id: ...} message triggers the cancel event."""
import asyncio

import pytest

from bridge import cancellation


@pytest.mark.asyncio
async def test_dispatch_cancel_sets_event(monkeypatch):
    # Arrange: register an in-flight stream
    event = cancellation.register_stream("msg_abc")
    assert not event.is_set()

    # Act: simulate what the server does when it sees {cancel:true, id:"msg_abc"}
    from bridge.server import _dispatch_cancel
    result = _dispatch_cancel({"cancel": True, "id": "msg_abc"})

    # Assert
    assert result is True
    assert event.is_set()
    cancellation.unregister_stream("msg_abc")


@pytest.mark.asyncio
async def test_dispatch_cancel_unknown_id_returns_false():
    from bridge.server import _dispatch_cancel
    result = _dispatch_cancel({"cancel": True, "id": "never_registered"})
    assert result is False


@pytest.mark.asyncio
async def test_dispatch_cancel_requires_true_flag():
    from bridge.server import _dispatch_cancel
    result = _dispatch_cancel({"cancel": False, "id": "x"})
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_server_cancel_routing.py -v`
Expected: FAIL — `ImportError: cannot import name '_dispatch_cancel' from 'bridge.server'`.

- [ ] **Step 3: Implement**

Edit `bridge/server.py`. Add near the top, after the existing imports:

```python
from bridge import cancellation
```

Insert this helper just above `_handle_message`:

```python
def _dispatch_cancel(msg: dict) -> bool:
    """If *msg* is a cancel message, trigger the cancellation event.

    Returns True if a known stream was cancelled, False otherwise (including
    when the message is not a cancel message at all).
    """
    if not msg.get("cancel"):
        return False
    msg_id = msg.get("id")
    if not isinstance(msg_id, str) or not msg_id:
        return False
    return cancellation.cancel_stream(msg_id)
```

Modify `_handle_message` to handle cancel before the normal dispatch. Replace the existing try/parse block (beginning with `try: msg = json.loads(raw)`) with:

```python
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await _send_json(ws, {
            "id": None,
            "type": "error",
            "data": {"message": "Invalid JSON"},
        })
        return

    # Cancellation shortcut: {cancel: true, id: <in-flight-id>}
    if msg.get("cancel"):
        cancelled = _dispatch_cancel(msg)
        await _send_json(ws, {
            "id": msg.get("id"),
            "type": "cancel_ack",
            "data": {"cancelled": cancelled},
        })
        return

    msg_id = msg.get("id")
    msg_type = msg.get("type")
    data = msg.get("data", {})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_server_cancel_routing.py -v`
Expected: PASS — 3/3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/server.py bridge/tests/test_server_cancel_routing.py
git commit -m "feat(bridge): route {cancel:true,id} messages to cancellation registry"
```

---

## Phase 2 — handle_ai_chat

### Task 2.1: Session store with idle-eviction GC

**Files:**
- Create: `bridge/session_store.py`
- Create: `bridge/tests/test_session_store.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_session_store.py`:

```python
import asyncio
import time

import pytest

from bridge.session_store import SessionStore


@pytest.mark.asyncio
async def test_append_and_get():
    store = SessionStore(idle_ttl_seconds=60)
    await store.append("s1", {"role": "user", "content": "hi"})
    await store.append("s1", {"role": "assistant", "content": "hello"})
    history = await store.get("s1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "hello"


@pytest.mark.asyncio
async def test_get_unknown_session_returns_empty_list():
    store = SessionStore(idle_ttl_seconds=60)
    history = await store.get("nope")
    assert history == []


@pytest.mark.asyncio
async def test_clear_session():
    store = SessionStore(idle_ttl_seconds=60)
    await store.append("s2", {"role": "user", "content": "x"})
    await store.clear("s2")
    assert await store.get("s2") == []


@pytest.mark.asyncio
async def test_idle_eviction_with_fake_clock():
    """Sessions idle for more than TTL are evicted by sweep()."""
    t = [1000.0]
    store = SessionStore(idle_ttl_seconds=60, clock=lambda: t[0])
    await store.append("s3", {"role": "user", "content": "x"})
    # Still fresh
    t[0] = 1030.0
    await store.sweep()
    assert await store.get("s3") != []
    # Now idle beyond TTL
    t[0] = 1200.0
    await store.sweep()
    assert await store.get("s3") == []


@pytest.mark.asyncio
async def test_append_refreshes_last_active():
    t = [500.0]
    store = SessionStore(idle_ttl_seconds=60, clock=lambda: t[0])
    await store.append("s4", {"role": "user", "content": "x"})
    t[0] = 590.0
    await store.append("s4", {"role": "user", "content": "y"})  # refresh
    t[0] = 640.0  # 50s after last append -> still fresh
    await store.sweep()
    assert len(await store.get("s4")) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_session_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.session_store'`.

- [ ] **Step 3: Implement**

Create `bridge/session_store.py`:

```python
"""In-memory chat session store with idle-eviction.

Sessions are identified by frontend-generated session_id strings.
Lost on bridge restart (deliberate - per design spec).
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable


class SessionStore:
    """Async-safe session map keyed by session_id.

    Each entry holds the conversation history (list of {role, content} dicts)
    plus a last_active timestamp. Call sweep() periodically to evict idle
    sessions; or call start_gc_task(interval_seconds) to have the store run
    its own background task.
    """

    def __init__(
        self,
        *,
        idle_ttl_seconds: float = 3600.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._sessions: dict[str, dict] = {}  # id -> {"history": [...], "last_active": float}
        self._lock = asyncio.Lock()
        self._idle_ttl = idle_ttl_seconds
        self._clock = clock or time.monotonic
        self._gc_task: asyncio.Task | None = None

    async def append(self, session_id: str, turn: dict) -> None:
        async with self._lock:
            entry = self._sessions.setdefault(
                session_id, {"history": [], "last_active": self._clock()}
            )
            entry["history"].append(turn)
            entry["last_active"] = self._clock()

    async def get(self, session_id: str) -> list[dict]:
        async with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return []
            entry["last_active"] = self._clock()
            return list(entry["history"])

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def sweep(self) -> int:
        """Evict sessions idle longer than idle_ttl_seconds. Return eviction count."""
        now = self._clock()
        async with self._lock:
            stale = [sid for sid, e in self._sessions.items()
                     if now - e["last_active"] > self._idle_ttl]
            for sid in stale:
                del self._sessions[sid]
            return len(stale)

    async def _gc_loop(self, interval_seconds: float) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self.sweep()
            except Exception:  # pragma: no cover - defensive
                pass

    def start_gc_task(self, interval_seconds: float = 300.0) -> None:
        """Spawn a background task that periodically sweeps idle sessions."""
        if self._gc_task is None or self._gc_task.done():
            self._gc_task = asyncio.create_task(self._gc_loop(interval_seconds))


# Module-level default store used by handle_ai_chat
default_store = SessionStore(idle_ttl_seconds=3600.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_session_store.py -v`
Expected: PASS — 5/5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/session_store.py bridge/tests/test_session_store.py
git commit -m "feat(bridge): in-memory SessionStore with idle-eviction GC"
```

---

### Task 2.2: Prompt builders (ai_chat)

**Files:**
- Create: `bridge/prompts.py`
- Create: `bridge/tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_prompts.py`:

```python
from bridge.prompts import (
    CLAUDE_MD_DIGEST,
    AI_CHAT_BASELINE,
    build_ai_chat_system_prompt,
)


def test_claude_md_digest_has_core_rules():
    # Digest MUST reference the non-negotiable Deluge rules.
    for rule in [
        "zoho.loginuser",
        "thisapp.permissions.isUserInRole",
        "Added_User",
        "ifnull",
        "999.99",
        "Compliance_Config",
        "Estimated_Carbon_KG",
        "double quotes",
    ]:
        assert rule in CLAUDE_MD_DIGEST, f"digest missing {rule!r}"


def test_ai_chat_baseline_role():
    assert "Zoho Creator" in AI_CHAT_BASELINE
    assert "Deluge" in AI_CHAT_BASELINE


def test_build_ai_chat_system_prompt_without_context():
    sp = build_ai_chat_system_prompt(ds_summary=None)
    assert AI_CHAT_BASELINE in sp
    assert CLAUDE_MD_DIGEST in sp
    assert "Current app context" not in sp


def test_build_ai_chat_system_prompt_with_context():
    sp = build_ai_chat_system_prompt(ds_summary="5 forms, 12 workflows")
    assert "Current app context: 5 forms, 12 workflows" in sp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.prompts'`.

- [ ] **Step 3: Implement**

Create `bridge/prompts.py`:

```python
"""System-prompt builders used by the Claude-backed handlers."""
from __future__ import annotations


AI_CHAT_BASELINE = (
    "You are a senior Zoho Creator / Deluge engineer embedded in the ForgeDS IDE. "
    "You help the user build, debug, and refine their Zoho Creator app. "
    "Follow all project conventions strictly."
)


# Distilled from CLAUDE.md at the repo root. Updated here when CLAUDE.md changes.
CLAUDE_MD_DIGEST = """PROJECT CONVENTIONS (Deluge / Zoho Creator):

Strings
- Use double quotes only. Never single quotes. Single quotes are for date literals.

Null-safety
- Always guard query results: glRec != null && glRec.count() > 0.
- Use ifnull(value, fallback) for every query-result field access.

Roles
- Role checks use thisapp.permissions.isUserInRole("Role Name").
- zoho.loginuserrole does NOT exist.

Audit trail
- Every insert into approval_history MUST include Added_User = zoho.loginuser.
- Added_User only accepts zoho.loginuser or zoho.adminuser (NOT zoho.adminuserid).

Thresholds
- Fallback value is 999.99 (matches seed data), not 1000.

Missing builtins
- lpad() does NOT exist.
- hoursBetween is unavailable on Free-Trial daily schedules -- use daysBetween.

ESG / Compliance
- GL accounts carry ESG_Category and Carbon_Factor.
- On approval, populate ESG_Category + Estimated_Carbon_KG = input.amount_zar * carbonFactor.
- carbonFactor = ifnull(glRec.Carbon_Factor, 0) -- never assume GL record has ESG fields.
- Compliance_Config queries follow the pattern Config_Key == "KEY" && Active == true.

Custom API scripts
- NO input.FieldName, NO alert, NO cancel submit.
- Return data via response Map. The Link Name becomes the endpoint URL segment.

Syntax rules
- insert into field assignments use = (not :). sendmail / invokeUrl use :.
- Semicolons optional on most statements; required after action blocks.
"""


def build_ai_chat_system_prompt(ds_summary: str | None = None) -> str:
    """Compose the ai_chat system prompt from baseline + digest + optional context."""
    parts = [AI_CHAT_BASELINE, "", CLAUDE_MD_DIGEST]
    if ds_summary:
        parts += ["", f"Current app context: {ds_summary}"]
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_prompts.py -v`
Expected: PASS — 4/4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/prompts.py bridge/tests/test_prompts.py
git commit -m "feat(bridge): ai_chat system-prompt builder with CLAUDE.md digest"
```

---

### Task 2.3: Replace handle_ai_chat mock with streaming implementation

**Files:**
- Modify: `bridge/handlers.py`
- Modify: `bridge/server.py`
- Create: `bridge/tests/test_handle_ai_chat.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_handle_ai_chat.py`:

```python
"""Handler tests with a mocked AsyncAnthropic client."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bridge import handlers


class _FakeStream:
    def __init__(self, chunks, usage):
        self._chunks = chunks
        self._usage = usage

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def _iter_text(self):
        for c in self._chunks:
            yield c

    @property
    def text_stream(self):
        return self._iter_text()

    async def get_final_message(self):
        msg = MagicMock()
        msg.usage.input_tokens = self._usage["in"]
        msg.usage.output_tokens = self._usage["out"]
        msg.usage.cache_read_input_tokens = self._usage.get("cache", 0)
        return msg


def _fake_client(chunks, usage):
    client = MagicMock()
    stream = _FakeStream(chunks, usage)
    client.messages.stream = MagicMock(return_value=stream)
    return client


@pytest.mark.asyncio
async def test_ai_chat_returns_no_api_key_error_when_no_client(monkeypatch):
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: None)
    sends = []

    async def send(x):
        sends.append(x)

    result = await handlers.handle_ai_chat(
        {"id": "m1", "message": "hi", "session_id": "s"}, send_fn=send
    )
    assert result["code"] == "no_api_key"


@pytest.mark.asyncio
async def test_ai_chat_streams_chunks_and_returns_final(monkeypatch):
    client = _fake_client(["Hel", "lo ", "world"], {"in": 10, "out": 3, "cache": 5})
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    sends = []

    async def send(x):
        sends.append(x)

    result = await handlers.handle_ai_chat(
        {"id": "m2", "message": "Say hello", "session_id": "s2", "effort": "low"},
        send_fn=send,
    )

    assert [s["chunk"]["text"] for s in sends] == ["Hel", "lo ", "world"]
    assert result["response"] == "Hello world"
    assert result["model"] == "claude-haiku-4-5-20251001"
    assert result["session_id"] == "s2"
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 3, "cache_read_tokens": 5}


@pytest.mark.asyncio
async def test_ai_chat_history_grows(monkeypatch):
    client = _fake_client(["ok"], {"in": 1, "out": 1})
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    async def send(_):
        pass

    await handlers.handle_ai_chat(
        {"id": "m3", "message": "first", "session_id": "sx"}, send_fn=send
    )
    await handlers.handle_ai_chat(
        {"id": "m4", "message": "second", "session_id": "sx"}, send_fn=send
    )

    from bridge.session_store import default_store
    hist = await default_store.get("sx")
    # 2 user turns + 2 assistant turns
    assert len(hist) == 4
    assert hist[0]["role"] == "user"
    assert hist[1]["role"] == "assistant"
    assert hist[2]["content"] == "second"


@pytest.mark.asyncio
async def test_ai_chat_critique_injects_synthetic_turn(monkeypatch):
    captured = {}

    def stream_factory(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _FakeStream(["ok"], {"in": 1, "out": 1})

    client = MagicMock()
    client.messages.stream = stream_factory
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    # Pre-seed history with an assistant turn
    from bridge.session_store import default_store
    await default_store.clear("sc")
    await default_store.append("sc", {"role": "user", "content": "previous q"})
    await default_store.append("sc", {"role": "assistant", "content": "rejected answer"})

    async def send(_):
        pass

    await handlers.handle_ai_chat(
        {
            "id": "m5",
            "message": "new q",
            "session_id": "sc",
            "critique": "too vague, be specific",
        },
        send_fn=send,
    )

    msgs = captured["messages"]
    # Last 3 turns: assistant[rejected] + synthetic user + real user
    assert msgs[-3]["role"] == "assistant"
    assert "rejected answer" in msgs[-3]["content"]
    assert msgs[-2]["role"] == "user"
    assert "too vague, be specific" in msgs[-2]["content"]
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "new q"


@pytest.mark.asyncio
async def test_ai_chat_cancellation_between_chunks(monkeypatch):
    from bridge import cancellation

    async def slow_chunks():
        yield "first "
        # Cancel mid-stream
        cancellation.cancel_stream("m6")
        yield "second"

    class CancelStream(_FakeStream):
        @property
        def text_stream(self):
            return slow_chunks()

    client = MagicMock()
    client.messages.stream = MagicMock(return_value=CancelStream([], {"in": 1, "out": 1}))
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    sends = []

    async def send(x):
        sends.append(x)

    result = await handlers.handle_ai_chat(
        {"id": "m6", "message": "x", "session_id": "s6"}, send_fn=send
    )
    assert result["code"] == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_ai_chat.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_anthropic_client' from 'bridge.handlers'` (plus other failures because the mock handler doesn't accept `send_fn`).

- [ ] **Step 3: Implement**

In `bridge/handlers.py`, add new imports at the top (after existing imports):

```python
from bridge.claude_config import (
    build_anthropic_client,
    build_error,
    get_effort_config,
    no_api_key_error,
)
from bridge import cancellation
from bridge.session_store import default_store as _session_store
from bridge.prompts import build_ai_chat_system_prompt
```

Replace the existing `handle_ai_chat` function (lines 479–528) with:

```python
async def handle_ai_chat(data: dict, send_fn: SendFn | None = None) -> dict:
    """Stream a Claude response for the user's message.

    Writes chunks to *send_fn* and returns the final response dict.
    """
    message = data.get("message")
    session_id = data.get("session_id")
    if not isinstance(message, str) or not message.strip():
        return build_error("Missing required field: message", "invalid_request")
    if not isinstance(session_id, str) or not session_id.strip():
        return build_error("Missing required field: session_id", "invalid_request")

    client = build_anthropic_client()
    if client is None:
        return no_api_key_error()

    effort_config = get_effort_config(data.get("effort"))
    context = data.get("context") or {}
    system_prompt = build_ai_chat_system_prompt(ds_summary=context.get("ds_summary"))

    # Build conversation from session history + current request
    history = await _session_store.get(session_id)
    messages: list[dict] = list(history)

    critique = data.get("critique")
    if critique and history and history[-1].get("role") == "assistant":
        messages.append({
            "role": "user",
            "content": (
                "I didn't find that response useful. "
                f"Feedback: {critique}. Please revise."
            ),
        })

    messages.append({"role": "user", "content": message})

    message_id = data.get("id") or session_id
    cancel_event = cancellation.register_stream(message_id)

    collected: list[str] = []
    try:
        stream_kwargs: dict = {
            "model": effort_config["model"],
            "max_tokens": effort_config["max_tokens"],
            "system": [{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            "messages": messages,
        }
        if effort_config.get("thinking"):
            stream_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": effort_config["thinking"],
            }

        async with client.messages.stream(**stream_kwargs) as stream:
            async for text in stream.text_stream:
                if cancel_event.is_set():
                    return build_error("Client cancelled request.", "cancelled")
                collected.append(text)
                if send_fn is not None:
                    await send_fn({"chunk": {"text": text}})
            final = await stream.get_final_message()

        response_text = "".join(collected)

        # Persist both turns to history
        await _session_store.append(session_id, {"role": "user", "content": message})
        await _session_store.append(session_id, {"role": "assistant", "content": response_text})

        usage = {
            "input_tokens": getattr(final.usage, "input_tokens", 0),
            "output_tokens": getattr(final.usage, "output_tokens", 0),
            "cache_read_tokens": getattr(final.usage, "cache_read_input_tokens", 0),
        }
        return {
            "response": response_text,
            "model": effort_config["model"],
            "session_id": session_id,
            "usage": usage,
        }
    except Exception as exc:
        log_error({"source": "handle_ai_chat", "message": str(exc), "request_id": message_id})
        name = type(exc).__name__.lower()
        if "rate" in name and "limit" in name:
            return build_error("Rate limited by Anthropic API.", "rate_limited")
        if "timeout" in name:
            return build_error("Upstream request timed out.", "timeout")
        return build_error(f"Upstream error: {exc}", "upstream_error")
    finally:
        cancellation.unregister_stream(message_id)
```

Update `bridge/server.py` — change the ai_chat dispatch branch to pass `send_fn`. Replace:

```python
        elif msg_type == "ai_chat":
            result = await handle_ai_chat(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})
```

with:

```python
        elif msg_type == "ai_chat":
            async def send_ai_stream(chunk_data: dict) -> None:
                await _send_json(ws, {"id": msg_id, "type": "stream", "data": chunk_data})

            payload = {**data, "id": msg_id}
            result = await handle_ai_chat(payload, send_fn=send_ai_stream)
            await _send_json(ws, {"id": msg_id, "type": "stream_end", "data": {"result": result}})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_ai_chat.py -v`
Expected: PASS — 5/5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/handlers.py bridge/server.py bridge/tests/test_handle_ai_chat.py
git commit -m "feat(bridge): replace handle_ai_chat mock with streaming Claude handler"
```

---

### Task 2.4: Live-API smoke test gated by ANTHROPIC_API_KEY

**Files:**
- Create: `bridge/tests/live_api/__init__.py`
- Create: `bridge/tests/live_api/test_live_smoke.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/live_api/__init__.py` (empty). Create `bridge/tests/live_api/test_live_smoke.py`:

```python
"""Live-API smoke tests. Skipped when ANTHROPIC_API_KEY is absent."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- live-API tests skipped",
)


@pytest.mark.asyncio
async def test_live_ai_chat_returns_ifnull_when_asked_about_null_guard():
    from bridge import handlers

    chunks = []

    async def send(x):
        chunks.append(x)

    result = await handlers.handle_ai_chat(
        {
            "id": "live_1",
            "message": (
                "In Deluge, how should I safely read a field from a query result "
                "that might be null? One sentence."
            ),
            "session_id": "live_smoke_session",
            "effort": "low",
        },
        send_fn=send,
    )
    assert "response" in result, f"expected response, got {result}"
    assert "ifnull" in result["response"].lower()
```

- [ ] **Step 2: Run test to verify it skips (or passes if key is set)**

Without key: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/live_api/ -v`
Expected: SKIPPED — 1 skipped with reason "ANTHROPIC_API_KEY not set".

With key (optional, at engineer's discretion, costs a few tokens):
`ANTHROPIC_API_KEY=sk-ant-... python -m pytest bridge/tests/live_api/ -v`
Expected: PASS.

- [ ] **Step 3: Implement** — already complete in Step 1 (the test is the deliverable).

- [ ] **Step 4: Run test to verify it passes** — see Step 2 above.

- [ ] **Step 5: Commit**

```bash
git add bridge/tests/live_api/__init__.py bridge/tests/live_api/test_live_smoke.py
git commit -m "test(bridge): add live-API smoke test for handle_ai_chat (gated by env key)"
```

---

## Phase 3 — handle_refine_prompt

### Task 3.1: refine_prompt system-prompt builder

**Files:**
- Modify: `bridge/prompts.py`
- Modify: `bridge/tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_prompts.py`:

```python
from bridge.prompts import build_refine_prompt_system_prompt, REFINE_PROMPT_SCHEMA_EXAMPLE


def test_schema_example_has_all_five_sections():
    for sid in ["forms", "workflows", "reports", "approvals", "apis"]:
        assert f'"id": "{sid}"' in REFINE_PROMPT_SCHEMA_EXAMPLE


def test_build_refine_prompt_system_prompt_contains_schema_and_rules():
    sp = build_refine_prompt_system_prompt()
    assert "sections" in sp
    assert REFINE_PROMPT_SCHEMA_EXAMPLE in sp
    # Must instruct Claude to output JSON only
    assert "JSON" in sp or "json" in sp
    # Must reference project conventions
    assert "Added_User" in sp or "Compliance_Config" in sp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_prompts.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_refine_prompt_system_prompt'`.

- [ ] **Step 3: Implement**

Append to `bridge/prompts.py`:

```python
# ---------------------------------------------------------------------------
# refine_prompt
# ---------------------------------------------------------------------------

REFINE_PROMPT_SCHEMA_EXAMPLE = """{
  "sections": [
    {
      "id": "forms",
      "title": "Forms",
      "icon": "[F]",
      "content": "The forms to be created for this app.",
      "items": ["Expense_Claims", "GL_Accounts", "Approval_History"],
      "isEditable": true
    },
    {
      "id": "workflows",
      "title": "Workflows",
      "icon": "[W]",
      "content": "Event-driven scripts attached to form lifecycles.",
      "items": ["on_submit_validate", "on_approval_update", "auto_populate_esg"],
      "isEditable": true
    },
    {
      "id": "reports",
      "title": "Reports & Dashboards",
      "icon": "[R]",
      "content": "Reporting views for claims and audit trails.",
      "items": ["All_Claims", "Pending_Approvals", "Approval_Audit_Trail"],
      "isEditable": true
    },
    {
      "id": "approvals",
      "title": "Approval Processes",
      "icon": "[A]",
      "content": "Multi-level approval workflow with segregation of duties.",
      "items": ["Line Manager Approval", "HoD Approval"],
      "isEditable": true
    },
    {
      "id": "apis",
      "title": "API Endpoints",
      "icon": "[API]",
      "content": "Custom API endpoints for external integrations.",
      "items": ["Get_Dashboard_Summary", "Get_Claim_Status"],
      "isEditable": true
    }
  ]
}"""


REFINE_PROMPT_BASELINE = (
    "You are a senior Zoho Creator solution architect. "
    "Given a raw app idea, produce a structured Zoho Creator project specification "
    "with exactly five sections: forms, workflows, reports, approvals, apis. "
    "Output ONLY a fenced JSON block (no prose before or after) matching the schema below."
)


def build_refine_prompt_system_prompt() -> str:
    """System prompt for refine_prompt: baseline + conventions digest + schema example."""
    parts = [
        REFINE_PROMPT_BASELINE,
        "",
        CLAUDE_MD_DIGEST,
        "",
        "OUTPUT SCHEMA (return a fenced ```json block matching this exact shape):",
        REFINE_PROMPT_SCHEMA_EXAMPLE,
    ]
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_prompts.py -v`
Expected: PASS — 6/6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/prompts.py bridge/tests/test_prompts.py
git commit -m "feat(bridge): add refine_prompt system-prompt + sections-schema example"
```

---

### Task 3.2: JSON extraction + validation helper

**Files:**
- Modify: `bridge/handlers.py`
- Create: `bridge/tests/test_refine_prompt.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_refine_prompt.py`:

```python
import pytest

from bridge.handlers import _extract_sections_json


def test_extract_plain_json():
    raw = '{"sections": [{"id": "forms", "title": "F", "items": []}]}'
    parsed = _extract_sections_json(raw)
    assert parsed["sections"][0]["id"] == "forms"


def test_extract_fenced_json():
    raw = 'Some prose.\n```json\n{"sections": [{"id": "forms", "title": "F", "items": []}]}\n```\nTrailing.'
    parsed = _extract_sections_json(raw)
    assert parsed["sections"][0]["id"] == "forms"


def test_extract_fenced_without_language_tag():
    raw = "```\n{\"sections\": [{\"id\": \"x\", \"title\": \"T\", \"items\": []}]}\n```"
    parsed = _extract_sections_json(raw)
    assert parsed["sections"][0]["id"] == "x"


def test_extract_rejects_non_json():
    with pytest.raises(ValueError):
        _extract_sections_json("no JSON anywhere in this text")


def test_extract_rejects_missing_sections_key():
    with pytest.raises(ValueError):
        _extract_sections_json('{"other": []}')


def test_extract_rejects_missing_section_id():
    with pytest.raises(ValueError):
        _extract_sections_json('{"sections": [{"title": "no id"}]}')


def test_extract_requires_all_five_section_ids():
    # Only forms present -- must fail validation
    with pytest.raises(ValueError):
        _extract_sections_json(
            '{"sections": [{"id": "forms", "title": "F", "items": []}]}',
            require_all=True,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_refine_prompt.py -v`
Expected: FAIL — `ImportError: cannot import name '_extract_sections_json'`.

- [ ] **Step 3: Implement**

Append to `bridge/handlers.py`:

```python
# ---------------------------------------------------------------------------
# refine_prompt helpers
# ---------------------------------------------------------------------------
import json as _json
import re as _re

_FENCED_JSON = _re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", _re.DOTALL)
_REQUIRED_SECTION_IDS = {"forms", "workflows", "reports", "approvals", "apis"}


def _extract_sections_json(raw: str, *, require_all: bool = False) -> dict:
    """Extract + validate the sections spec from a Claude response.

    Accepts either a fenced ```json block or a bare JSON object. Raises
    ValueError if parsing or validation fails.
    """
    text = raw.strip()

    # 1. Try fenced block first
    m = _FENCED_JSON.search(text)
    if m:
        candidate = m.group(1)
    else:
        # 2. Bare JSON object - find first { and matching last }
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise ValueError("No JSON object found in response")
        candidate = text[first : last + 1]

    try:
        parsed = _json.loads(candidate)
    except _json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc

    if not isinstance(parsed, dict) or "sections" not in parsed:
        raise ValueError("Response missing required 'sections' key")
    sections = parsed["sections"]
    if not isinstance(sections, list) or not sections:
        raise ValueError("'sections' must be a non-empty list")

    seen_ids: set[str] = set()
    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ValueError(f"Section {idx} is not an object")
        sid = sec.get("id")
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"Section {idx} missing 'id'")
        if not isinstance(sec.get("title", ""), str):
            raise ValueError(f"Section {idx} has non-string title")
        if not isinstance(sec.get("items", []), list):
            raise ValueError(f"Section {idx} items is not a list")
        seen_ids.add(sid)

    if require_all and not _REQUIRED_SECTION_IDS.issubset(seen_ids):
        missing = _REQUIRED_SECTION_IDS - seen_ids
        raise ValueError(f"Response missing required sections: {sorted(missing)}")

    return parsed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_refine_prompt.py -v`
Expected: PASS — 7/7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/handlers.py bridge/tests/test_refine_prompt.py
git commit -m "feat(bridge): add _extract_sections_json with fenced/bare JSON tolerance"
```

---

### Task 3.3: Replace handle_refine_prompt mock with Claude handler

**Files:**
- Modify: `bridge/handlers.py`
- Modify: `bridge/tests/test_refine_prompt.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_refine_prompt.py`:

```python
from unittest.mock import MagicMock

from bridge import handlers


def _fake_messages_create(text: str):
    """Build a fake AsyncAnthropic.messages.create coroutine returning *text*."""

    async def _create(**kwargs):
        msg = MagicMock()
        msg.content = [MagicMock(type="text", text=text)]
        return msg

    return _create


VALID_JSON = """```json
{
  "sections": [
    {"id": "forms", "title": "Forms", "icon": "[F]", "content": "...", "items": ["A","B"], "isEditable": true},
    {"id": "workflows", "title": "Workflows", "icon": "[W]", "content": "...", "items": ["w"], "isEditable": true},
    {"id": "reports", "title": "Reports", "icon": "[R]", "content": "...", "items": ["r"], "isEditable": true},
    {"id": "approvals", "title": "Approvals", "icon": "[A]", "content": "...", "items": ["ap"], "isEditable": true},
    {"id": "apis", "title": "APIs", "icon": "[API]", "content": "...", "items": ["api"], "isEditable": true}
  ]
}
```"""


@pytest.mark.asyncio
async def test_refine_prompt_no_api_key(monkeypatch):
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: None)
    result = await handlers.handle_refine_prompt({"prompt": "expense app"})
    assert result["code"] == "no_api_key"


@pytest.mark.asyncio
async def test_refine_prompt_happy_path(monkeypatch):
    client = MagicMock()
    client.messages.create = _fake_messages_create(VALID_JSON)
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    result = await handlers.handle_refine_prompt({"prompt": "expense app"})
    ids = [s["id"] for s in result["sections"]]
    assert ids == ["forms", "workflows", "reports", "approvals", "apis"]


@pytest.mark.asyncio
async def test_refine_prompt_retry_on_bad_json(monkeypatch):
    """First call returns garbage; retry returns valid JSON."""
    calls = {"n": 0}

    async def _create(**kwargs):
        calls["n"] += 1
        msg = MagicMock()
        if calls["n"] == 1:
            msg.content = [MagicMock(type="text", text="not json at all")]
        else:
            msg.content = [MagicMock(type="text", text=VALID_JSON)]
        return msg

    client = MagicMock()
    client.messages.create = _create
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    result = await handlers.handle_refine_prompt({"prompt": "expense app"})
    assert "sections" in result
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_refine_prompt_second_failure_returns_parse_error(monkeypatch):
    async def _create(**kwargs):
        msg = MagicMock()
        msg.content = [MagicMock(type="text", text="still not json")]
        return msg

    client = MagicMock()
    client.messages.create = _create
    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: client)

    result = await handlers.handle_refine_prompt({"prompt": "x"})
    assert result["code"] == "parse_error"
    assert "raw_response" in result["details"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_refine_prompt.py -v`
Expected: FAIL — the current mock handler returns hardcoded sections regardless of input; the tests expect real Claude routing + parse_error codepath.

- [ ] **Step 3: Implement**

Add imports at top of `bridge/handlers.py` if not already present:

```python
from bridge.prompts import build_refine_prompt_system_prompt
from bridge.claude_config import DEFAULT_APP_CREATION_EFFORT
```

Replace the existing `handle_refine_prompt` function with:

```python
async def handle_refine_prompt(data: dict) -> dict:
    """Convert raw idea text into a structured Zoho Creator sections spec."""
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return build_error("Missing required field: prompt", "invalid_request")

    client = build_anthropic_client()
    if client is None:
        return no_api_key_error()

    effort_config = get_effort_config(data.get("effort") or DEFAULT_APP_CREATION_EFFORT)
    system_prompt = build_refine_prompt_system_prompt()

    user_turn_parts: list[str] = []
    critique = data.get("critique")
    prior = data.get("prior_output")
    if critique and prior:
        user_turn_parts.append("Previous output you produced:")
        user_turn_parts.append(_json.dumps(prior, indent=2))
        user_turn_parts.append("")
        user_turn_parts.append(f"The user rejected this with feedback: {critique}")
        user_turn_parts.append("")
    user_turn_parts.append(f"New idea: {prompt.strip()}")
    user_turn_parts.append("")
    user_turn_parts.append("Produce the sections specification as a fenced ```json block.")

    user_content = "\n".join(user_turn_parts)

    last_raw = ""
    for attempt in range(2):
        if attempt == 1:
            user_content += (
                "\n\nYour previous output was not valid JSON matching the schema. "
                "Return ONLY a fenced ```json block with all five sections "
                "(forms, workflows, reports, approvals, apis)."
            )
        try:
            create_kwargs: dict = {
                "model": effort_config["model"],
                "max_tokens": effort_config["max_tokens"],
                "system": [{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                "messages": [{"role": "user", "content": user_content}],
            }
            if effort_config.get("thinking"):
                create_kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": effort_config["thinking"],
                }
            msg = await client.messages.create(**create_kwargs)
            raw = "".join(
                getattr(block, "text", "")
                for block in (msg.content or [])
                if getattr(block, "type", "") == "text"
            )
            last_raw = raw
            return _extract_sections_json(raw, require_all=True)
        except ValueError:
            continue  # retry once
        except Exception as exc:
            log_error({"source": "handle_refine_prompt", "message": str(exc)})
            return build_error(f"Upstream error: {exc}", "upstream_error")

    return build_error(
        "Could not parse model response into sections schema after retry.",
        "parse_error",
        details={"raw_response": last_raw[:2000]},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_refine_prompt.py -v`
Expected: PASS — 11/11 tests pass (7 helper + 4 handler).

- [ ] **Step 5: Commit**

```bash
git add bridge/handlers.py bridge/tests/test_refine_prompt.py
git commit -m "feat(bridge): replace handle_refine_prompt mock with Claude + JSON retry loop"
```

---

## Phase 4 — handle_inspect_element

### Task 4.1: RelationshipGraph dataclasses

**Files:**
- Create: `bridge/relationship_builder.py`
- Create: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_relationship_builder.py`:

```python
import pytest

from bridge.relationship_builder import NodeInfo, Edge, Usage, RelationshipGraph


def test_node_info_fields():
    n = NodeInfo(id="form:F", element_type="form", display_name="F", properties={"k": 1})
    assert n.id == "form:F"
    assert n.element_type == "form"
    assert n.properties["k"] == 1


def test_edge_defaults_metadata_to_empty():
    e = Edge(source="a", target="b", edge_type="form_has_field")
    assert e.metadata == {}


def test_usage_shape():
    u = Usage(identifier="Amount_ZAR", file="f.dg", line=3, context="x = input.Amount_ZAR;")
    assert u.line == 3


def test_relationship_graph_defaults():
    g = RelationshipGraph()
    assert g.nodes == {}
    assert g.edges == []
    assert g.usages == {}
    assert g.external_refs == set()


def test_relationship_graph_accepts_populated_fields():
    n = NodeInfo(id="form:F", element_type="form", display_name="F", properties={})
    e = Edge(source="form:F", target="workflow:W", edge_type="form_has_workflow")
    u = Usage(identifier="F", file="x.dg", line=1, context="")
    g = RelationshipGraph(
        nodes={n.id: n},
        edges=[e],
        usages={"F": [u]},
        external_refs={"Missing_Form"},
    )
    assert g.nodes["form:F"].display_name == "F"
    assert g.edges[0].edge_type == "form_has_workflow"
    assert "Missing_Form" in g.external_refs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.relationship_builder'`.

- [ ] **Step 3: Implement**

Create `bridge/relationship_builder.py`:

```python
"""Relationship graph builder: form/field/workflow/schedule/approval nodes + edges.

Consumes DSParser output plus per-script Deluge AST (via forgeds.lang).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Graph schema (per spec section 5.3)
# ---------------------------------------------------------------------------

@dataclass
class NodeInfo:
    id: str                        # stable ID e.g. "form:Expense_Claims"
    element_type: str              # "form" | "field" | "workflow" | "schedule" | "approval" | "report" | "api" | "function"
    display_name: str
    properties: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str                    # NodeInfo.id
    target: str                    # NodeInfo.id or external ref
    edge_type: str                 # enumerated (see spec section 5.4)
    metadata: dict = field(default_factory=dict)


@dataclass
class Usage:
    identifier: str
    file: str
    line: int
    context: str


@dataclass
class RelationshipGraph:
    nodes: dict[str, NodeInfo] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    usages: dict[str, list[Usage]] = field(default_factory=dict)
    external_refs: set[str] = field(default_factory=set)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: PASS — 5/5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/relationship_builder.py bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): RelationshipGraph dataclasses (NodeInfo, Edge, Usage)"
```

---

### Task 4.2: Node extraction from DSParser output

**Files:**
- Modify: `bridge/relationship_builder.py`
- Create: `bridge/tests/fixtures/tiny_app.ds`
- Modify: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/fixtures/tiny_app.ds` with a minimal 2-form, 2-workflow structure:

```text
/*
 * ForgeDS test fixture
 */
 application "Tiny App"
 {
	date format = "dd-MMM-yyyy"
	time zone = "Africa/Johannesburg"
	time format = "24-hr"

		forms
		{
			form Expense_Claims
			{
				displayname = "Expense Claims"
				Claim_ID as "Claim ID"
				{
					type = number
				}
				Amount_ZAR as "Amount (ZAR)"
				{
					type = decimal
				}
				GL_Account as "GL Account"
				{
					type = lookup
				}
				Status as "Status"
				{
					type = picklist
				}
			}

			form GL_Accounts
			{
				displayname = "GL Accounts"
				GL_Code as "GL Code"
				{
					type = text
				}
				Carbon_Factor as "Carbon Factor"
				{
					type = decimal
				}
			}
		}


		workflow
		{
		form
		{
			on_validate as "On Validate"
			{
				type =  form
				form = Expense_Claims

				record event = on add or edit

				on validate
				{
					actions
					{
						custom deluge script
						(
							claimAmt = input.Amount_ZAR;
							glRec = GL_Accounts[ID == input.GL_Account];
							if (glRec != null && glRec.count() > 0)
							{
								info "ok";
							}
						)
					}
				}

			}
			on_success as "On Success"
			{
				type =  form
				form = Expense_Claims

				record event = on add or edit

				on success
				{
					actions
					{
						custom deluge script
						(
							input.Status = "Submitted";
							row = insert into Approval_History
							[
								Claim = input.Claim_ID
								Added_User = zoho.loginuser
							];
						)
					}
				}

			}
		}
		}
	}
```

Append to `bridge/tests/test_relationship_builder.py`:

```python
from pathlib import Path

from bridge.relationship_builder import extract_nodes


FIXTURE = Path(__file__).parent / "fixtures" / "tiny_app.ds"


def _parse_fixture():
    import sys

    forgeds_src = str(Path(__file__).resolve().parents[2] / "src")
    if forgeds_src not in sys.path:
        sys.path.insert(0, forgeds_src)
    from forgeds.core.parse_ds_export import DSParser

    parser = DSParser(FIXTURE.read_text(encoding="utf-8"))
    parser.parse()
    return parser


def test_extract_nodes_has_form_and_field_nodes():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)

    assert "form:Expense_Claims" in nodes
    assert "form:GL_Accounts" in nodes
    assert nodes["form:Expense_Claims"].element_type == "form"


def test_extract_nodes_has_field_nodes_scoped_to_form():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    assert "field:Expense_Claims.Amount_ZAR" in nodes
    assert "field:Expense_Claims.Claim_ID" in nodes
    assert "field:GL_Accounts.Carbon_Factor" in nodes
    assert nodes["field:Expense_Claims.Amount_ZAR"].element_type == "field"


def test_extract_nodes_has_workflow_nodes():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    wf_ids = [k for k in nodes if k.startswith("workflow:")]
    assert len(wf_ids) >= 2
    any_wf = nodes[wf_ids[0]]
    assert "form" in any_wf.properties
    assert "trigger" in any_wf.properties
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_nodes'`.

- [ ] **Step 3: Implement**

Append to `bridge/relationship_builder.py`:

```python
# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return name.strip()


def _script_node_type(script: Any) -> str:
    ctx = getattr(script, "context", "")
    if ctx == "form-workflow":
        return "workflow"
    if ctx == "scheduled":
        return "schedule"
    if ctx == "approval":
        return "approval"
    if ctx == "custom-api":
        return "api"
    return "workflow"


def extract_nodes(forms: list, scripts: list) -> dict[str, NodeInfo]:
    """Build the initial node table from DSParser FormDef / ScriptDef objects."""
    nodes: dict[str, NodeInfo] = {}

    for form in forms:
        fname = _slug(form.name)
        form_id = f"form:{fname}"
        nodes[form_id] = NodeInfo(
            id=form_id,
            element_type="form",
            display_name=form.display_name or fname,
            properties={
                "fieldCount": len(form.fields),
                "fields": [f.link_name for f in form.fields],
            },
        )
        for fld in form.fields:
            fld_id = f"field:{fname}.{fld.link_name}"
            nodes[fld_id] = NodeInfo(
                id=fld_id,
                element_type="field",
                display_name=fld.display_name or fld.link_name,
                properties={
                    "type": fld.field_type,
                    "form": fname,
                    "notes": getattr(fld, "notes", ""),
                },
            )

    for script in scripts:
        ntype = _script_node_type(script)
        node_id = f"{ntype}:{script.name}"
        nodes[node_id] = NodeInfo(
            id=node_id,
            element_type=ntype,
            display_name=script.display_name or script.name,
            properties={
                "form": getattr(script, "form", ""),
                "trigger": getattr(script, "trigger", ""),
                "event": getattr(script, "event", ""),
                "context": getattr(script, "context", ""),
            },
        )

    return nodes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: PASS — 8/8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/relationship_builder.py bridge/tests/fixtures/tiny_app.ds bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): extract_nodes builds form/field/workflow/schedule/approval/api nodes"
```

---

### Task 4.3: AST-walk helper for Deluge scripts

The forgeds.lang public API (verified in source):
- `forgeds.lang.lexer.Lexer(source).tokenize()` returns `list[Token]`.
- `forgeds.lang.parser.Parser(tokens).parse()` returns a `forgeds.lang.ast_nodes.Program`.
- Key AST nodes: `Program, Assignment, FormQuery(form, criteria), InsertStmt(table, params), FieldAccess(object, field), Identifier(name), FunctionCall(callee, args)`. Base class `Visitor` has `visit()` + `generic_visit()`.

**Files:**
- Modify: `bridge/relationship_builder.py`
- Modify: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_relationship_builder.py`:

```python
from bridge.relationship_builder import walk_script, ScriptWalkResult


def test_walk_script_detects_form_query():
    code = """
glRec = GL_Accounts[ID == input.GL_Account];
"""
    res = walk_script("on_validate.dg", code)
    assert isinstance(res, ScriptWalkResult)
    assert "GL_Accounts" in res.queried_forms


def test_walk_script_detects_insert():
    code = """
row = insert into Approval_History
[
    Claim = input.Claim_ID
    Added_User = zoho.loginuser
];
"""
    res = walk_script("approve.dg", code)
    assert "Approval_History" in res.inserted_forms


def test_walk_script_detects_field_reads():
    code = """
x = input.Amount_ZAR;
y = input.GL_Account + 1;
"""
    res = walk_script("f.dg", code)
    assert ("input", "Amount_ZAR") in res.field_reads
    assert ("input", "GL_Account") in res.field_reads


def test_walk_script_detects_field_writes():
    code = """
input.Status = "Submitted";
input.Estimated_Carbon_KG = 10;
"""
    res = walk_script("w.dg", code)
    assert ("input", "Status") in res.field_writes
    assert ("input", "Estimated_Carbon_KG") in res.field_writes


def test_walk_script_collects_usages_with_lines():
    code = "x = input.Amount_ZAR;\ny = input.Status;"
    res = walk_script("u.dg", code)
    lines = [u.line for u in res.usages if u.identifier == "Amount_ZAR"]
    assert 1 in lines


def test_walk_script_falls_back_to_regex_on_parse_error(monkeypatch):
    """If the Deluge parser explodes, walker must still return a result."""
    import bridge.relationship_builder as rb

    def boom(self):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr("forgeds.lang.parser.Parser.parse", boom)

    code = "glRec = GL_Accounts[ID == input.X];"
    res = rb.walk_script("fb.dg", code)
    assert "GL_Accounts" in res.queried_forms
    assert res.used_fallback is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ImportError: cannot import name 'walk_script'`.

- [ ] **Step 3: Implement**

Append to `bridge/relationship_builder.py`:

```python
# ---------------------------------------------------------------------------
# AST walker (forgeds.lang) + regex fallback
# ---------------------------------------------------------------------------
import re as _rb_re
import sys as _rb_sys
from dataclasses import dataclass as _rb_dataclass, field as _rb_field
from pathlib import Path as _rb_Path


def _ensure_forgeds_path() -> None:
    src = str(_rb_Path(__file__).resolve().parent.parent / "src")
    if src not in _rb_sys.path:
        _rb_sys.path.insert(0, src)


@_rb_dataclass
class ScriptWalkResult:
    file: str
    queried_forms: list[str] = _rb_field(default_factory=list)
    inserted_forms: list[str] = _rb_field(default_factory=list)
    field_reads: list[tuple[str, str]] = _rb_field(default_factory=list)   # (container, field)
    field_writes: list[tuple[str, str]] = _rb_field(default_factory=list)  # (container, field)
    function_calls: list[str] = _rb_field(default_factory=list)
    usages: list[Usage] = _rb_field(default_factory=list)
    used_fallback: bool = False


def _walk_with_ast(file: str, code: str) -> ScriptWalkResult:
    _ensure_forgeds_path()
    from forgeds.lang.lexer import Lexer
    from forgeds.lang.parser import Parser
    from forgeds.lang import ast_nodes as ast

    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()

    result = ScriptWalkResult(file=file)
    source_lines = code.splitlines()

    def _ctx_line(node) -> tuple[int, str]:
        span = getattr(node, "span", None)
        line = getattr(span, "start_line", getattr(span, "line", 0)) if span else 0
        line = line or 0
        if 0 < line <= len(source_lines):
            return line, source_lines[line - 1].strip()
        return line, ""

    class _Walker(ast.Visitor):
        def visit_FormQuery(self, node):
            if node.form and node.form not in result.queried_forms:
                result.queried_forms.append(node.form)
            line, ctx = _ctx_line(node)
            result.usages.append(Usage(identifier=node.form, file=file, line=line, context=ctx))
            if node.criteria is not None:
                self.visit(node.criteria)

        def visit_InsertStmt(self, node):
            if node.table and node.table not in result.inserted_forms:
                result.inserted_forms.append(node.table)
            line, ctx = _ctx_line(node)
            result.usages.append(Usage(identifier=node.table, file=file, line=line, context=ctx))
            self.visit(node.params)

        def visit_FieldAccess(self, node):
            container = getattr(getattr(node, "object", None), "name", None)
            if container in {"input", "rec", "row"} and isinstance(node.field, str):
                pair = (container, node.field)
                if pair not in result.field_reads:
                    result.field_reads.append(pair)
                line, ctx = _ctx_line(node)
                result.usages.append(Usage(identifier=node.field, file=file, line=line, context=ctx))
            self.generic_visit(node)

        def visit_Assignment(self, node):
            tgt = node.target
            if isinstance(tgt, ast.FieldAccess):
                container = getattr(getattr(tgt, "object", None), "name", None)
                if container in {"input", "rec", "row"} and isinstance(tgt.field, str):
                    pair = (container, tgt.field)
                    if pair not in result.field_writes:
                        result.field_writes.append(pair)
            # Recurse into RHS for reads
            self.visit(node.value)

        def visit_FunctionCall(self, node):
            callee = node.callee
            name = getattr(callee, "name", None) or getattr(callee, "field", None)
            if isinstance(name, str) and name not in result.function_calls:
                result.function_calls.append(name)
            self.generic_visit(node)

    _Walker().visit(program)
    return result


_RE_FORM_QUERY = _rb_re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\[")
_RE_INSERT_INTO = _rb_re.compile(r"insert\s+into\s+([A-Za-z_][A-Za-z0-9_]*)")
_RE_FIELD_ACCESS = _rb_re.compile(r"\b(input|rec|row)\.([A-Za-z_][A-Za-z0-9_]*)")
_RE_FIELD_WRITE = _rb_re.compile(r"\b(input|rec|row)\.([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)")


def _walk_with_regex(file: str, code: str) -> ScriptWalkResult:
    result = ScriptWalkResult(file=file, used_fallback=True)
    for lineno, line in enumerate(code.splitlines(), start=1):
        for m in _RE_FORM_QUERY.finditer(line):
            form_name = m.group(1)
            if form_name not in result.queried_forms:
                result.queried_forms.append(form_name)
            result.usages.append(Usage(identifier=form_name, file=file, line=lineno, context=line.strip()))
        for m in _RE_INSERT_INTO.finditer(line):
            t = m.group(1)
            if t not in result.inserted_forms:
                result.inserted_forms.append(t)
            result.usages.append(Usage(identifier=t, file=file, line=lineno, context=line.strip()))
        writes_on_line: set[tuple[str, str]] = set()
        for m in _RE_FIELD_WRITE.finditer(line):
            pair = (m.group(1), m.group(2))
            writes_on_line.add(pair)
            if pair not in result.field_writes:
                result.field_writes.append(pair)
            result.usages.append(Usage(identifier=pair[1], file=file, line=lineno, context=line.strip()))
        for m in _RE_FIELD_ACCESS.finditer(line):
            pair = (m.group(1), m.group(2))
            if pair in writes_on_line:
                continue
            if pair not in result.field_reads:
                result.field_reads.append(pair)
            result.usages.append(Usage(identifier=pair[1], file=file, line=lineno, context=line.strip()))
    return result


def walk_script(file: str, code: str) -> ScriptWalkResult:
    """Walk a Deluge script body via forgeds.lang AST; fall back to regex on failure."""
    try:
        return _walk_with_ast(file, code)
    except Exception:
        return _walk_with_regex(file, code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: PASS — 14/14 tests pass (8 previous + 6 walker).

- [ ] **Step 5: Commit**

```bash
git add bridge/relationship_builder.py bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): walk_script AST walker with regex fallback for Deluge scripts"
```

---

### Task 4.4: Edge extraction

**Files:**
- Modify: `bridge/relationship_builder.py`
- Modify: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_relationship_builder.py`:

```python
from bridge.relationship_builder import build_edges


def test_build_edges_form_has_field():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    edges = build_edges(nodes, parser.scripts)
    etypes = {(e.source, e.target, e.edge_type) for e in edges}
    assert ("form:Expense_Claims", "field:Expense_Claims.Amount_ZAR", "form_has_field") in etypes


def test_build_edges_form_has_workflow_and_triggered_on():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    edges = build_edges(nodes, parser.scripts)
    assert any(
        e.edge_type == "form_has_workflow"
        and e.source == "form:Expense_Claims"
        and e.target.startswith("workflow:")
        for e in edges
    )
    assert any(
        e.edge_type == "workflow_triggered_on"
        and e.target == "form:Expense_Claims"
        for e in edges
    )


def test_build_edges_workflow_queries_form():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    edges = build_edges(nodes, parser.scripts)
    # GL_Accounts query becomes a workflow_references_gl edge per spec 5.4
    assert any(
        (e.edge_type == "workflow_queries_form" or e.edge_type == "workflow_references_gl")
        and e.target == "form:GL_Accounts"
        for e in edges
    )


def test_build_edges_workflow_inserts_into_external_ref():
    """Approval_History is not in tiny_app.ds -> unresolved external edge."""
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    edges = build_edges(nodes, parser.scripts)
    unresolved = [
        e for e in edges
        if e.edge_type == "workflow_inserts_into"
        and e.metadata.get("unresolved") is True
    ]
    assert any("Approval_History" in e.target for e in unresolved)


def test_build_edges_field_read_by_and_written_by():
    parser = _parse_fixture()
    nodes = extract_nodes(parser.forms, parser.scripts)
    edges = build_edges(nodes, parser.scripts)
    assert any(
        e.edge_type == "field_read_by"
        and e.source == "field:Expense_Claims.Amount_ZAR"
        for e in edges
    )
    assert any(
        e.edge_type == "field_written_by"
        and e.source.endswith(".Status")
        for e in edges
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_edges'`.

- [ ] **Step 3: Implement**

Append to `bridge/relationship_builder.py`:

```python
# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------

_SPECIAL_QUERY_FORMS = {
    "GL_Accounts": "workflow_references_gl",
    "Compliance_Config": "workflow_references_config_key",
}


def _resolve_form(nodes: dict[str, NodeInfo], form_name: str) -> str | None:
    key = f"form:{form_name}"
    return key if key in nodes else None


def _resolve_field(nodes: dict[str, NodeInfo], form_name: str, field_name: str) -> str | None:
    key = f"field:{form_name}.{field_name}"
    return key if key in nodes else None


def build_edges(nodes: dict[str, NodeInfo], scripts: list) -> list[Edge]:
    """Build edge list per spec 5.4.

    Side-effect-free: call repeatedly on same nodes+scripts to rebuild.
    """
    edges: list[Edge] = []

    # form_has_field
    for node_id, node in list(nodes.items()):
        if node.element_type == "form":
            fname = node_id.split(":", 1)[1]
            for fld in node.properties.get("fields", []):
                target = f"field:{fname}.{fld}"
                edges.append(Edge(source=node_id, target=target, edge_type="form_has_field"))

    # form_has_workflow / schedule / approval / api
    for script in scripts:
        ntype = _script_node_type(script)
        node_id = f"{ntype}:{script.name}"
        form_name = getattr(script, "form", "") or ""
        form_ref = _resolve_form(nodes, form_name)
        if form_ref:
            edge_type = f"form_has_{ntype}"
            edges.append(Edge(source=form_ref, target=node_id, edge_type=edge_type))
            if ntype == "workflow":
                edges.append(Edge(
                    source=node_id, target=form_ref, edge_type="workflow_triggered_on",
                    metadata={
                        "trigger": getattr(script, "trigger", ""),
                        "event": getattr(script, "event", ""),
                    },
                ))
            elif ntype == "schedule":
                edges.append(Edge(source=node_id, target=form_ref, edge_type="schedule_targets_form"))
            elif ntype == "approval":
                edges.append(Edge(source=node_id, target=form_ref, edge_type="approval_reviews_form"))
            elif ntype == "api":
                edges.append(Edge(source=node_id, target=form_ref, edge_type="api_queries_form"))

    # Per-script AST walk for queries/inserts/field reads/writes
    for script in scripts:
        ntype = _script_node_type(script)
        node_id = f"{ntype}:{script.name}"
        file_label = f"{script.name}.dg"
        walk = walk_script(file_label, getattr(script, "code", "") or "")

        script_form = getattr(script, "form", "") or ""

        for qform in walk.queried_forms:
            target = _resolve_form(nodes, qform) or qform
            unresolved = target == qform
            etype = _SPECIAL_QUERY_FORMS.get(qform, "workflow_queries_form")
            edges.append(Edge(
                source=node_id, target=target, edge_type=etype,
                metadata={"unresolved": unresolved} if unresolved else {},
            ))

        for iform in walk.inserted_forms:
            target = _resolve_form(nodes, iform) or iform
            unresolved = target == iform
            edges.append(Edge(
                source=node_id, target=target, edge_type="workflow_inserts_into",
                metadata={"unresolved": unresolved} if unresolved else {},
            ))

        for container, fname in walk.field_reads:
            fld_id = _resolve_field(nodes, script_form, fname) if container == "input" else None
            if fld_id is None:
                for k, n in nodes.items():
                    if n.element_type == "field" and k.endswith(f".{fname}"):
                        fld_id = k
                        break
            if fld_id:
                edges.append(Edge(source=fld_id, target=node_id, edge_type="field_read_by"))

        for container, fname in walk.field_writes:
            fld_id = _resolve_field(nodes, script_form, fname) if container == "input" else None
            if fld_id is None:
                for k, n in nodes.items():
                    if n.element_type == "field" and k.endswith(f".{fname}"):
                        fld_id = k
                        break
            if fld_id:
                edges.append(Edge(source=fld_id, target=node_id, edge_type="field_written_by"))

    return edges
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: PASS — 19/19 tests pass (14 prior + 5 new edges).

- [ ] **Step 5: Commit**

```bash
git add bridge/relationship_builder.py bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): build_edges produces all enumerated edge types (queries, inserts, reads, writes)"
```

---

### Task 4.5: Usages index + external refs + build_graph entrypoint

**Files:**
- Modify: `bridge/relationship_builder.py`
- Modify: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_relationship_builder.py`:

```python
from bridge.relationship_builder import build_graph


def test_build_graph_returns_populated_graph():
    parser = _parse_fixture()
    g = build_graph(parser.forms, parser.scripts)

    assert "form:Expense_Claims" in g.nodes
    assert len(g.edges) > 0
    assert "GL_Accounts" in g.usages
    assert any(u.line > 0 for u in g.usages["GL_Accounts"])


def test_build_graph_populates_external_refs():
    parser = _parse_fixture()
    g = build_graph(parser.forms, parser.scripts)
    assert "Approval_History" in g.external_refs


def test_build_graph_usages_include_context_string():
    parser = _parse_fixture()
    g = build_graph(parser.forms, parser.scripts)
    all_contexts = [u.context for uses in g.usages.values() for u in uses]
    assert any("input.Amount_ZAR" in c for c in all_contexts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_graph'`.

- [ ] **Step 3: Implement**

Append to `bridge/relationship_builder.py`:

```python
# ---------------------------------------------------------------------------
# Top-level build entry point
# ---------------------------------------------------------------------------

def build_graph(forms: list, scripts: list) -> RelationshipGraph:
    """Build the full RelationshipGraph from parsed forms + scripts."""
    nodes = extract_nodes(forms, scripts)
    edges = build_edges(nodes, scripts)

    usages: dict[str, list[Usage]] = {}
    for script in scripts:
        file_label = f"{script.name}.dg"
        walk = walk_script(file_label, getattr(script, "code", "") or "")
        for u in walk.usages:
            usages.setdefault(u.identifier, []).append(u)

    external: set[str] = set()
    for e in edges:
        if e.metadata.get("unresolved"):
            external.add(e.target)

    return RelationshipGraph(nodes=nodes, edges=edges, usages=usages, external_refs=external)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_relationship_builder.py -v`
Expected: PASS — all tests pass including 3 new (22 total).

- [ ] **Step 5: Commit**

```bash
git add bridge/relationship_builder.py bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): build_graph aggregates nodes/edges/usages/external_refs"
```

---

### Task 4.6: Wire graph build into parse_ds, store per-session

**Files:**
- Create: `bridge/graph_store.py`
- Modify: `bridge/handlers.py` (parse_ds hookup)
- Create: `bridge/tests/test_graph_store.py`
- Modify: `bridge/tests/test_relationship_builder.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_graph_store.py`:

```python
import pytest

from bridge.graph_store import put_graph, get_graph, drop_graph


@pytest.mark.asyncio
async def test_put_and_get():
    payload = {"nodes": {}, "edges": []}
    await put_graph("s1", payload)
    assert await get_graph("s1") is payload


@pytest.mark.asyncio
async def test_get_missing_returns_none():
    assert await get_graph("never") is None


@pytest.mark.asyncio
async def test_drop_graph():
    await put_graph("s2", {"nodes": {}})
    await drop_graph("s2")
    assert await get_graph("s2") is None
```

Also extend `bridge/tests/test_relationship_builder.py` with a parse_ds hookup test:

```python
@pytest.mark.asyncio
async def test_handle_parse_ds_builds_graph_and_surfaces_enrichment():
    from bridge.handlers import handle_parse_ds
    from bridge.graph_store import get_graph

    fixture_content = FIXTURE.read_text(encoding="utf-8")
    session_id = "s_parse_test"

    result = await handle_parse_ds({
        "content": fixture_content,
        "session_id": session_id,
    })
    assert "tree" in result
    assert result.get("enrichmentLevel") == "bridge-enriched"
    assert "graphSummary" in result
    assert result["graphSummary"]["nodeCount"] > 0

    graph = await get_graph(session_id)
    assert graph is not None
    assert "form:Expense_Claims" in graph.nodes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_graph_store.py bridge/tests/test_relationship_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.graph_store'` + parse_ds hookup test fails.

- [ ] **Step 3: Implement**

Create `bridge/graph_store.py`:

```python
"""Per-session RelationshipGraph cache used by handle_inspect_element."""
from __future__ import annotations

import asyncio
from typing import Any

_graphs: dict[str, Any] = {}
_lock = asyncio.Lock()


async def put_graph(session_id: str, graph: Any) -> None:
    async with _lock:
        _graphs[session_id] = graph


async def get_graph(session_id: str) -> Any | None:
    async with _lock:
        return _graphs.get(session_id)


async def drop_graph(session_id: str) -> None:
    async with _lock:
        _graphs.pop(session_id, None)
```

Modify `bridge/handlers.py` `handle_parse_ds` to build the graph after parsing. Replace the existing function body (from the `parser = DSParser(content)` line through `return build_tree_response(...)`) with:

```python
    try:
        parser = DSParser(content)
        parser.parse()
    except Exception as e:
        return {"error": f"Parse error: {e}"}

    response = build_tree_response(parser.forms, parser.scripts, file_path)

    # Bridge-side enrichment: build relationship graph + surface counts
    from bridge.relationship_builder import build_graph
    from bridge import graph_store

    graph = build_graph(parser.forms, parser.scripts)
    session_id = data.get("session_id") or "default"
    await graph_store.put_graph(session_id, graph)

    response["enrichmentLevel"] = "bridge-enriched"
    response["graphSummary"] = {
        "nodeCount": len(graph.nodes),
        "edgeCount": len(graph.edges),
        "externalRefCount": len(graph.external_refs),
    }
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_graph_store.py bridge/tests/test_relationship_builder.py -v`
Expected: PASS — graph_store 3 tests + all relationship_builder tests (including parse_ds hookup).

- [ ] **Step 5: Commit**

```bash
git add bridge/graph_store.py bridge/handlers.py bridge/tests/test_graph_store.py bridge/tests/test_relationship_builder.py
git commit -m "feat(bridge): store per-session RelationshipGraph at parse_ds completion"
```

---

### Task 4.7: Replace handle_inspect_element mock with graph-lookup

**Files:**
- Modify: `bridge/handlers.py`
- Create: `bridge/tests/test_handle_inspect_element.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_handle_inspect_element.py`:

```python
from pathlib import Path

import pytest

from bridge.handlers import handle_parse_ds, handle_inspect_element


FIXTURE = Path(__file__).parent / "fixtures" / "tiny_app.ds"
SESSION = "inspect_test_session"


async def _seed_graph():
    await handle_parse_ds({
        "content": FIXTURE.read_text(encoding="utf-8"),
        "session_id": SESSION,
    })


@pytest.mark.asyncio
async def test_inspect_unknown_session_returns_not_found():
    result = await handle_inspect_element({
        "session_id": "never",
        "element_id": "form:X",
        "element_type": "form",
    })
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_inspect_form_returns_fields_and_relationships():
    await _seed_graph()
    result = await handle_inspect_element({
        "session_id": SESSION,
        "element_id": "form:Expense_Claims",
        "element_type": "form",
    })
    assert result["properties"]["displayName"] == "Expense Claims"
    assert result["properties"]["enrichmentLevel"] == "bridge-enriched"
    field_names = [f["name"] for f in result["fields"]]
    assert "Amount_ZAR" in field_names
    rel_types = [r["type"] for r in result["relationships"]]
    assert "form_has_workflow" in rel_types


@pytest.mark.asyncio
async def test_inspect_field_returns_usages():
    await _seed_graph()
    result = await handle_inspect_element({
        "session_id": SESSION,
        "element_id": "field:Expense_Claims.Amount_ZAR",
        "element_type": "field",
    })
    assert result["properties"]["form"] == "Expense_Claims"
    usages = result.get("usages", [])
    assert any("Amount_ZAR" in u["context"] for u in usages)


@pytest.mark.asyncio
async def test_inspect_workflow_returns_relationships():
    await _seed_graph()
    from bridge.graph_store import get_graph
    g = await get_graph(SESSION)
    wf_id = next(k for k, n in g.nodes.items() if n.element_type == "workflow")

    result = await handle_inspect_element({
        "session_id": SESSION,
        "element_id": wf_id,
        "element_type": "workflow",
    })
    rel_types = [r["type"] for r in result["relationships"]]
    assert "workflow_triggered_on" in rel_types


@pytest.mark.asyncio
async def test_inspect_unknown_element_id_returns_not_found():
    await _seed_graph()
    result = await handle_inspect_element({
        "session_id": SESSION,
        "element_id": "field:Nope.Missing",
        "element_type": "field",
    })
    assert result["code"] == "not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_inspect_element.py -v`
Expected: FAIL — existing mock returns hardcoded `_FIELD_INSPECTOR_DEFAULTS`; the graph-backed assertions fail.

- [ ] **Step 3: Implement**

In `bridge/handlers.py`, replace the entire `handle_inspect_element` function (and the `_FIELD_INSPECTOR_DEFAULTS` dict — it's no longer referenced) with:

```python
async def handle_inspect_element(data: dict) -> dict:
    """Look up an element in the parsed relationship graph and return its detail."""
    element_id = data.get("element_id")
    element_type = data.get("element_type")
    session_id = data.get("session_id")

    if not isinstance(element_id, str) or not element_id:
        return build_error("Missing required field: element_id", "invalid_request")
    if not isinstance(element_type, str) or not element_type:
        return build_error("Missing required field: element_type", "invalid_request")
    if not isinstance(session_id, str) or not session_id:
        return build_error("Missing required field: session_id", "invalid_request")

    from bridge import graph_store

    graph = await graph_store.get_graph(session_id)
    if graph is None:
        return build_error(
            "No parsed graph for this session. Call parse_ds first.",
            "not_found",
            details={"session_id": session_id},
        )

    node = graph.nodes.get(element_id)
    if node is None:
        return build_error(
            "Element not found in graph.",
            "not_found",
            details={"element_id": element_id, "element_type": element_type},
        )

    # Collect relationships: any edge touching this node
    relationships: list[dict] = []
    for e in graph.edges:
        if e.source == element_id:
            target_node = graph.nodes.get(e.target)
            relationships.append({
                "target": e.target,
                "targetName": target_node.display_name if target_node else e.target,
                "type": e.edge_type,
                "metadata": e.metadata,
            })
        elif e.target == element_id:
            source_node = graph.nodes.get(e.source)
            relationships.append({
                "target": e.source,
                "targetName": source_node.display_name if source_node else e.source,
                "type": e.edge_type,
                "direction": "inbound",
                "metadata": e.metadata,
            })

    # Element-type-specific response
    if element_type == "form":
        fname = element_id.split(":", 1)[1]
        fields = [
            {
                "id": k,
                "name": k.split(".", 1)[1] if "." in k else k,
                "type": n.properties.get("type", ""),
            }
            for k, n in graph.nodes.items()
            if n.element_type == "field" and k.startswith(f"field:{fname}.")
        ]
        has_wf = any(r["type"] == "form_has_workflow" for r in relationships)
        return {
            "properties": {
                "fieldCount": node.properties.get("fieldCount", len(fields)),
                "hasWorkflows": has_wf,
                "displayName": node.display_name,
                "enrichmentLevel": "bridge-enriched",
            },
            "fields": fields,
            "relationships": relationships,
            "usages": [],
        }

    if element_type == "field":
        short_name = element_id.split(".", 1)[1] if "." in element_id else element_id
        usages = graph.usages.get(short_name, [])
        return {
            "properties": {
                "type": node.properties.get("type", ""),
                "form": node.properties.get("form", ""),
                "displayName": node.display_name,
                "required": node.properties.get("required", False),
                "unique": node.properties.get("unique", False),
            },
            "relationships": relationships,
            "usages": [
                {"script": u.file, "line": u.line, "context": u.context}
                for u in usages
            ],
        }

    # workflow / schedule / approval / api / report / function — generic shape
    return {
        "properties": {
            **node.properties,
            "displayName": node.display_name,
            "enrichmentLevel": "bridge-enriched",
        },
        "relationships": relationships,
        "usages": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_inspect_element.py -v`
Expected: PASS — 5/5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/handlers.py bridge/tests/test_handle_inspect_element.py
git commit -m "feat(bridge): replace handle_inspect_element mock with graph-lookup"
```

---

## Phase 5 — handle_build_project

`forgeds.core` verified public surface:
- `forgeds.core.scaffold_deluge.scaffold_script(name, location, trigger, purpose, context, includes, *, kb_snippets=None) -> str` — importable, pure function.
- `forgeds.core.build_ds.emit_application(app_name, display_name, forms, reports, workflows, schedules) -> str` — importable, requires typed FormSpec/ReportSpec/WorkflowSpec/ScheduleSpec dataclasses.
- `forgeds.core.lint_deluge.lint_file(db, filepath)` — requires a `DelugeDB` instance + pre-built sqlite DB. Simpler to invoke via subprocess `python -m forgeds.core.lint_deluge <path>` (consistent with existing `handle_lint_check` pattern).

This plan calls `scaffold_script` directly and invokes the linter via `asyncio.create_subprocess_exec` (no shell). `emit_application` is intentionally NOT used here because scaffold mode produces .dg files + forgeds.yaml; .ds generation from scratch is deferred (not in spec scope).

### Task 5.1: GenerationPlan dataclass + plan_from_sections

**Files:**
- Create: `bridge/build_pipeline.py`
- Create: `bridge/tests/test_build_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_build_pipeline.py`:

```python
import pytest

from bridge.build_pipeline import GenerationPlan, plan_from_sections


def test_plan_from_sections_happy_path():
    sections = [
        {"id": "forms", "title": "Forms", "items": ["Expense_Claims", "GL_Accounts"]},
        {"id": "workflows", "title": "Workflows", "items": ["on_submit_validate", "on_approval_update"]},
        {"id": "reports", "title": "Reports", "items": ["All_Claims"]},
        {"id": "approvals", "title": "Approvals", "items": ["HoD Approval"]},
        {"id": "apis", "title": "APIs", "items": ["Get_Dashboard_Summary"]},
    ]
    plan = plan_from_sections(sections, project_name="Expense_Reimbursement")
    assert isinstance(plan, GenerationPlan)
    assert plan.project_name == "Expense_Reimbursement"
    assert plan.forms == ["Expense_Claims", "GL_Accounts"]
    assert plan.workflows[0] == ("Expense_Claims", "on_submit_validate")
    assert plan.reports == ["All_Claims"]
    assert plan.approvals == ["HoD Approval"]
    assert plan.apis == ["Get_Dashboard_Summary"]


def test_plan_from_sections_falls_back_to_title_for_project_name():
    sections = [{"id": "forms", "title": "Expense Stuff", "items": ["F"]}]
    plan = plan_from_sections(sections, project_name=None)
    assert plan.project_name == "Expense_Stuff"


def test_plan_from_sections_ignores_unknown_sections():
    sections = [
        {"id": "forms", "title": "Forms", "items": ["A"]},
        {"id": "unknown_thing", "title": "X", "items": ["Y"]},
    ]
    plan = plan_from_sections(sections, project_name="P")
    assert plan.forms == ["A"]
    assert plan.workflows == []
    assert plan.reports == []


def test_plan_from_sections_rejects_empty_sections():
    with pytest.raises(ValueError):
        plan_from_sections([], project_name=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.build_pipeline'`.

- [ ] **Step 3: Implement**

Create `bridge/build_pipeline.py`:

```python
"""Scaffold + fill pipeline for handle_build_project.

Scaffold mode: deterministic, invokes forgeds.core tooling (no Claude calls).
Fill mode: per-file Claude calls with lint validation + one retry on failure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_SECTION_FORMS = "forms"
_SECTION_WORKFLOWS = "workflows"
_SECTION_REPORTS = "reports"
_SECTION_APPROVALS = "approvals"
_SECTION_APIS = "apis"
_SECTION_SCHEDULES = "schedules"


@dataclass
class GenerationPlan:
    project_name: str
    forms: list[str] = field(default_factory=list)
    workflows: list[tuple[str, str]] = field(default_factory=list)  # (form_name, workflow_name)
    reports: list[str] = field(default_factory=list)
    apis: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    schedules: list[str] = field(default_factory=list)


def _sanitize_project_name(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "Untitled_App"


def plan_from_sections(sections: list[dict], *, project_name: str | None) -> GenerationPlan:
    """Convert a refine_prompt sections list into a GenerationPlan."""
    if not sections:
        raise ValueError("sections list is empty")

    by_id: dict[str, list[str]] = {}
    titles: list[str] = []
    for sec in sections:
        sid = sec.get("id", "")
        if not isinstance(sid, str):
            continue
        items_raw = sec.get("items", [])
        if not isinstance(items_raw, list):
            continue
        items = [str(x) for x in items_raw if isinstance(x, (str, int))]
        by_id[sid] = items
        title = sec.get("title", "")
        if isinstance(title, str):
            titles.append(title)

    resolved_name = project_name or (titles[0] if titles else "Untitled_App")
    resolved_name = _sanitize_project_name(resolved_name)

    forms = by_id.get(_SECTION_FORMS, [])
    default_form = forms[0] if forms else "Untitled_Form"

    workflows = [(default_form, name) for name in by_id.get(_SECTION_WORKFLOWS, [])]

    return GenerationPlan(
        project_name=resolved_name,
        forms=forms,
        workflows=workflows,
        reports=by_id.get(_SECTION_REPORTS, []),
        apis=by_id.get(_SECTION_APIS, []),
        approvals=by_id.get(_SECTION_APPROVALS, []),
        schedules=by_id.get(_SECTION_SCHEDULES, []),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: PASS — 4/4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/build_pipeline.py bridge/tests/test_build_pipeline.py
git commit -m "feat(bridge): GenerationPlan dataclass + plan_from_sections"
```

---

### Task 5.2: Scaffold pipeline

**Files:**
- Modify: `bridge/build_pipeline.py`
- Modify: `bridge/tests/test_build_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_build_pipeline.py`:

```python
from bridge.build_pipeline import scaffold, ScaffoldResult


@pytest.mark.asyncio
async def test_scaffold_returns_files_and_scaffold_id(tmp_path):
    from bridge.build_pipeline import GenerationPlan

    plan = GenerationPlan(
        project_name="Expense_Reimbursement",
        forms=["Expense_Claims", "GL_Accounts"],
        workflows=[("Expense_Claims", "on_submit_validate")],
        reports=["All_Claims"],
        apis=["Get_Dashboard_Summary"],
    )
    result = await scaffold(plan, output_root=tmp_path)
    assert isinstance(result, ScaffoldResult)
    assert result.scaffold_id.startswith("sc_")
    paths = [f["path"] for f in result.files]
    assert any(p.endswith("on_submit_validate.dg") for p in paths)
    assert any(p.endswith("Get_Dashboard_Summary.dg") for p in paths)
    assert any(p.endswith("forgeds.yaml") for p in paths)
    assert "errors" in result.lint_result
    assert "warnings" in result.lint_result


@pytest.mark.asyncio
async def test_scaffold_writes_deluge_skeleton_with_todo(tmp_path):
    from bridge.build_pipeline import GenerationPlan

    plan = GenerationPlan(
        project_name="P",
        forms=["FormA"],
        workflows=[("FormA", "wf_one")],
    )
    result = await scaffold(plan, output_root=tmp_path)
    wf = next(f for f in result.files if f["path"].endswith("wf_one.dg"))
    assert "TODO" in wf["content"]


@pytest.mark.asyncio
async def test_scaffold_emits_forgeds_yaml_with_scaffold_id(tmp_path):
    from bridge.build_pipeline import GenerationPlan

    plan = GenerationPlan(project_name="Xy", forms=["F"], workflows=[("F", "w")])
    result = await scaffold(plan, output_root=tmp_path)
    yaml_file = next(f for f in result.files if f["path"].endswith("forgeds.yaml"))
    assert 'name: "Xy"' in yaml_file["content"]
    assert result.scaffold_id in yaml_file["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'scaffold'`.

- [ ] **Step 3: Implement**

Append to `bridge/build_pipeline.py`:

```python
# ---------------------------------------------------------------------------
# Scaffold mode
# ---------------------------------------------------------------------------
import asyncio as _bp_asyncio
import sys as _bp_sys
import uuid as _bp_uuid
from dataclasses import dataclass as _bp_dataclass, field as _bp_field
from pathlib import Path as _bp_Path


@_bp_dataclass
class ScaffoldResult:
    scaffold_id: str
    project_name: str
    files: list[dict] = _bp_field(default_factory=list)
    lint_result: dict = _bp_field(default_factory=dict)


def _ensure_forgeds_on_path() -> None:
    src = str(_bp_Path(__file__).resolve().parent.parent / "src")
    if src not in _bp_sys.path:
        _bp_sys.path.insert(0, src)


def _new_scaffold_id() -> str:
    return "sc_" + _bp_uuid.uuid4().hex[:12]


def _scaffold_workflow_dg(workflow_name: str, form_name: str) -> str:
    """Generate a .dg skeleton via forgeds.core.scaffold_deluge.scaffold_script."""
    _ensure_forgeds_on_path()
    from forgeds.core.scaffold_deluge import scaffold_script

    return scaffold_script(
        name=f"{form_name}.{workflow_name}",
        location=f"Form > {form_name} > Workflow",
        trigger="On Add or Edit",
        purpose=f"TODO: scaffold for {workflow_name}",
        context="form-workflow",
        includes=[],
    )


def _scaffold_api_dg(api_name: str) -> str:
    _ensure_forgeds_on_path()
    from forgeds.core.scaffold_deluge import scaffold_script

    return scaffold_script(
        name=api_name,
        location=f"Microservices > Custom API > {api_name}",
        trigger="API invocation",
        purpose=f"TODO: implement {api_name}",
        context="custom-api",
        includes=[],
    )


def _render_forgeds_yaml(project_name: str, scaffold_id: str) -> str:
    return (
        "project:\n"
        f'  name: "{project_name}"\n'
        "  platform: zoho-creator\n"
        "  generated_by: ForgeDS IDE\n"
        f"  scaffold_id: {scaffold_id}\n"
    )


async def _run_lint_on_dir(target_dir: _bp_Path) -> dict:
    """Invoke `python -m forgeds.core.lint_deluge <target_dir>` and parse output."""
    cmd = [_bp_sys.executable, "-m", "forgeds.core.lint_deluge", str(target_dir)]
    try:
        proc = await _bp_asyncio.create_subprocess_exec(
            *cmd,
            stdout=_bp_asyncio.subprocess.PIPE,
            stderr=_bp_asyncio.subprocess.PIPE,
            cwd=str(_bp_Path(__file__).resolve().parent.parent),
        )
        stdout_bytes, _ = await _bp_asyncio.wait_for(proc.communicate(), timeout=30)
    except Exception as exc:
        return {"errors": 0, "warnings": 0, "details": [f"lint invocation failed: {exc}"]}

    stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
    errors = sum(1 for ln in stdout.splitlines() if ln.strip().startswith("E:"))
    warnings = sum(1 for ln in stdout.splitlines() if ln.strip().startswith("W:"))
    details = [ln for ln in stdout.splitlines() if ln.startswith(("E:", "W:", "I:"))]
    return {"errors": errors, "warnings": warnings, "details": details}


async def scaffold(plan: GenerationPlan, *, output_root: _bp_Path | None = None) -> ScaffoldResult:
    """Run the scaffold pipeline. *output_root* is the directory where skeleton files are written."""
    scaffold_id = _new_scaffold_id()

    if output_root is None:
        output_root = _bp_Path.cwd() / ".forgeds_scaffolds" / scaffold_id
    output_root = _bp_Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []

    # Workflows
    wf_dir = output_root / "src" / "deluge" / "form-workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    for form_name, wf_name in plan.workflows:
        content = _scaffold_workflow_dg(wf_name, form_name)
        path = f"src/deluge/form-workflows/{wf_name}.dg"
        (output_root / path).write_text(content, encoding="utf-8")
        files.append({
            "name": f"{wf_name}.dg", "path": path, "content": content, "language": "deluge",
        })

    # APIs
    api_dir = output_root / "src" / "deluge" / "custom-api"
    api_dir.mkdir(parents=True, exist_ok=True)
    for api_name in plan.apis:
        content = _scaffold_api_dg(api_name)
        path = f"src/deluge/custom-api/{api_name}.dg"
        (output_root / path).write_text(content, encoding="utf-8")
        files.append({
            "name": f"{api_name}.dg", "path": path, "content": content, "language": "deluge",
        })

    # forgeds.yaml
    yaml_content = _render_forgeds_yaml(plan.project_name, scaffold_id)
    (output_root / "forgeds.yaml").write_text(yaml_content, encoding="utf-8")
    files.append({
        "name": "forgeds.yaml", "path": "forgeds.yaml",
        "content": yaml_content, "language": "yaml",
    })

    lint_result = await _run_lint_on_dir(output_root / "src" / "deluge")

    return ScaffoldResult(
        scaffold_id=scaffold_id,
        project_name=plan.project_name,
        files=files,
        lint_result=lint_result,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: PASS — prior 4 + 3 scaffold tests = 7/7 pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/build_pipeline.py bridge/tests/test_build_pipeline.py
git commit -m "feat(bridge): scaffold pipeline invoking scaffold_deluge + subprocess lint"
```

---

### Task 5.3: Active scaffolds registry + TTL sweep

**Files:**
- Modify: `bridge/build_pipeline.py`
- Modify: `bridge/tests/test_build_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_build_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_scaffold_is_registered_for_fill(tmp_path):
    from bridge.build_pipeline import (
        GenerationPlan, scaffold, get_active_scaffold,
    )

    plan = GenerationPlan(project_name="P", forms=["F"], workflows=[("F", "w")])
    result = await scaffold(plan, output_root=tmp_path)
    found = get_active_scaffold(result.scaffold_id)
    assert found is not None
    assert found.project_name == "P"


@pytest.mark.asyncio
async def test_scaffold_registry_ttl_sweep(tmp_path):
    from bridge.build_pipeline import (
        GenerationPlan, scaffold, get_active_scaffold, sweep_active_scaffolds,
        _ACTIVE_SCAFFOLDS,
    )

    plan = GenerationPlan(project_name="P", forms=["F"], workflows=[("F", "w")])
    result = await scaffold(plan, output_root=tmp_path)
    sid = result.scaffold_id

    # Artificially age the entry
    entry = _ACTIVE_SCAFFOLDS[sid]
    entry["created_at"] -= 24 * 3600 + 1  # 1 second past TTL

    swept = sweep_active_scaffolds(ttl_seconds=24 * 3600)
    assert sid in swept
    assert get_active_scaffold(sid) is None


def test_get_unknown_scaffold_returns_none():
    from bridge.build_pipeline import get_active_scaffold
    assert get_active_scaffold("sc_nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_active_scaffold'`.

- [ ] **Step 3: Implement**

Append to `bridge/build_pipeline.py`:

```python
# ---------------------------------------------------------------------------
# Active scaffolds registry
# ---------------------------------------------------------------------------
import time as _bp_time

_ACTIVE_SCAFFOLDS: dict[str, dict] = {}
# scaffold_id -> {"plan": GenerationPlan, "output_root": str, "created_at": float}


def register_scaffold(scaffold_id: str, plan: GenerationPlan, output_root: _bp_Path) -> None:
    _ACTIVE_SCAFFOLDS[scaffold_id] = {
        "plan": plan,
        "output_root": str(output_root),
        "created_at": _bp_time.monotonic(),
    }


def get_active_scaffold(scaffold_id: str) -> GenerationPlan | None:
    entry = _ACTIVE_SCAFFOLDS.get(scaffold_id)
    if entry is None:
        return None
    return entry["plan"]


def sweep_active_scaffolds(*, ttl_seconds: float = 24 * 3600.0) -> list[str]:
    """Drop entries older than *ttl_seconds*. Return the evicted scaffold_ids."""
    now = _bp_time.monotonic()
    evicted: list[str] = []
    for sid in list(_ACTIVE_SCAFFOLDS.keys()):
        if now - _ACTIVE_SCAFFOLDS[sid]["created_at"] > ttl_seconds:
            _ACTIVE_SCAFFOLDS.pop(sid, None)
            evicted.append(sid)
    return evicted
```

Then, inside the `scaffold(...)` function, right after `output_root.mkdir(parents=True, exist_ok=True)`, insert:

```python
    register_scaffold(scaffold_id, plan, output_root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: PASS — 10/10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/build_pipeline.py bridge/tests/test_build_pipeline.py
git commit -m "feat(bridge): active scaffolds registry with 24h TTL sweep"
```

---

### Task 5.4: Fill pipeline (per-file Claude + lint retry)

**Files:**
- Modify: `bridge/build_pipeline.py`
- Modify: `bridge/tests/test_build_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `bridge/tests/test_build_pipeline.py`:

```python
from unittest.mock import MagicMock


def _fake_claude_client(per_file_text: dict[str, str]):
    """Return a client whose messages.create yields text keyed by filename marker in the prompt."""

    async def _create(**kwargs):
        user_content = ""
        for m in kwargs.get("messages", []):
            if m.get("role") == "user":
                user_content = m.get("content", "")
        chosen = ""
        for fname, text in per_file_text.items():
            if fname in user_content:
                chosen = text
                break
        msg = MagicMock()
        msg.content = [MagicMock(type="text", text=chosen)]
        return msg

    client = MagicMock()
    client.messages.create = _create
    return client


@pytest.mark.asyncio
async def test_fill_success_replaces_stubs(tmp_path, monkeypatch):
    from bridge.build_pipeline import GenerationPlan, scaffold, fill

    plan = GenerationPlan(project_name="P", forms=["F"], workflows=[("F", "my_wf")])
    scaffolded = await scaffold(plan, output_root=tmp_path)

    valid_code = '```deluge\nclaimAmt = ifnull(input.Amount_ZAR, 0);\n```'
    client = _fake_claude_client({"my_wf.dg": valid_code})

    async def fake_lint(path):
        return {"errors": 0, "warnings": 0, "details": []}
    monkeypatch.setattr("bridge.build_pipeline._run_lint_on_file", fake_lint)

    result = await fill(
        scaffolded,
        sections=[{"id": "workflows", "items": ["my_wf"]}],
        effort="low",
        client=client,
    )
    assert result["status"] in ("success", "partial_success")
    filled_wf = next(f for f in result["files"] if f["name"] == "my_wf.dg")
    assert "ifnull(input.Amount_ZAR" in filled_wf["content"]


@pytest.mark.asyncio
async def test_fill_retries_on_lint_error_then_gives_up(tmp_path, monkeypatch):
    from bridge.build_pipeline import GenerationPlan, scaffold, fill

    plan = GenerationPlan(project_name="P", forms=["F"], workflows=[("F", "bad_wf")])
    scaffolded = await scaffold(plan, output_root=tmp_path)

    client = _fake_claude_client({"bad_wf.dg": '```deluge\nx = "broken";\n```'})

    calls = {"n": 0}

    async def fake_lint(path):
        calls["n"] += 1
        return {"errors": 1, "warnings": 0, "details": ["E: bad_wf.dg:1 -- synthetic failure"]}
    monkeypatch.setattr("bridge.build_pipeline._run_lint_on_file", fake_lint)

    result = await fill(
        scaffolded,
        sections=[{"id": "workflows", "items": ["bad_wf"]}],
        effort="low",
        client=client,
    )
    assert calls["n"] >= 2  # retried at least once
    assert result["status"] == "partial_success"
    assert any(err["code"] == "lint_failed" for err in result["errors"])
    filled_wf = next(f for f in result["files"] if f["name"] == "bad_wf.dg")
    assert "TODO" in filled_wf["content"]


@pytest.mark.asyncio
async def test_fill_requires_known_scaffold_id():
    from bridge.build_pipeline import fill, ScaffoldResult

    bogus = ScaffoldResult(scaffold_id="sc_unknown", project_name="X", files=[], lint_result={})
    result = await fill(bogus, sections=[], effort="low", client=MagicMock())
    assert result["status"] == "error"
    assert result["code"] == "not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'fill'`.

- [ ] **Step 3: Implement**

Append to `bridge/build_pipeline.py`:

```python
# ---------------------------------------------------------------------------
# Fill mode
# ---------------------------------------------------------------------------
import re as _bp_re2


_FENCED_CODE = _bp_re2.compile(r"```(?:deluge|dg)?\s*(.*?)```", _bp_re2.DOTALL)


def _extract_code(raw: str) -> str:
    m = _FENCED_CODE.search(raw)
    return m.group(1).strip() if m else raw.strip()


async def _run_lint_on_file(path: _bp_Path) -> dict:
    """Lint a single .dg file via subprocess; return structured summary."""
    cmd = [_bp_sys.executable, "-m", "forgeds.core.lint_deluge", str(path)]
    try:
        proc = await _bp_asyncio.create_subprocess_exec(
            *cmd,
            stdout=_bp_asyncio.subprocess.PIPE,
            stderr=_bp_asyncio.subprocess.PIPE,
            cwd=str(_bp_Path(__file__).resolve().parent.parent),
        )
        stdout_bytes, _ = await _bp_asyncio.wait_for(proc.communicate(), timeout=30)
    except Exception as exc:
        return {"errors": 1, "warnings": 0, "details": [f"lint invocation failed: {exc}"]}

    stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
    errors = sum(1 for ln in stdout.splitlines() if ln.strip().startswith("E:"))
    warnings = sum(1 for ln in stdout.splitlines() if ln.strip().startswith("W:"))
    details = [ln for ln in stdout.splitlines() if ln.startswith(("E:", "W:", "I:"))]
    return {"errors": errors, "warnings": warnings, "details": details}


def _fill_system_prompt() -> str:
    from bridge.prompts import CLAUDE_MD_DIGEST
    return (
        "You are filling in a Zoho Creator Deluge script for a ForgeDS scaffold.\n"
        "Output ONLY a fenced ```deluge block containing the final script body.\n"
        "Do not include the original scaffold header comment in your output; "
        "just produce the script body.\n\n"
        + CLAUDE_MD_DIGEST
    )


async def _claude_fill_one(
    client, *, effort: str, file_name: str, scaffold_body: str,
    section_context: str, lint_feedback: str | None,
) -> str:
    from bridge.claude_config import get_effort_config

    cfg = get_effort_config(effort)
    system = _fill_system_prompt()
    parts = [
        f"File: {file_name}",
        "",
        "Scaffold currently contains:",
        "```deluge",
        scaffold_body,
        "```",
        "",
        f"Intended purpose for this section: {section_context}",
    ]
    if lint_feedback:
        parts += ["", f"Previous attempt failed lint. Errors: {lint_feedback}", "Please fix."]
    create_kwargs: dict = {
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "\n".join(parts)}],
    }
    if cfg.get("thinking"):
        create_kwargs["thinking"] = {"type": "enabled", "budget_tokens": cfg["thinking"]}
    msg = await client.messages.create(**create_kwargs)
    raw = "".join(
        getattr(block, "text", "")
        for block in (msg.content or [])
        if getattr(block, "type", "") == "text"
    )
    return _extract_code(raw)


async def fill(
    scaffolded: ScaffoldResult,
    *,
    sections: list[dict],
    effort: str,
    client,
    progress_cb=None,
) -> dict:
    """Per-file Claude generation with one lint-driven retry.

    Returns a response dict mirroring handle_build_project's fill-mode shape.
    """
    if get_active_scaffold(scaffolded.scaffold_id) is None:
        return {
            "status": "error",
            "code": "not_found",
            "error": f"Scaffold {scaffolded.scaffold_id} not found or expired.",
            "files": scaffolded.files,
            "errors": [{
                "step": "validate", "code": "not_found",
                "message": "scaffold_id unknown",
            }],
        }

    scaffold_files = {f["name"]: dict(f) for f in scaffolded.files}

    # Map section items to filenames by convention
    section_by_item: dict[str, str] = {}
    for sec in sections:
        for item in sec.get("items", []):
            if sec.get("id") == "workflows":
                section_by_item[f"{item}.dg"] = f"workflows: {item}"
            elif sec.get("id") == "apis":
                section_by_item[f"{item}.dg"] = f"apis: {item}"

    errors: list[dict] = []

    reg_entry = _ACTIVE_SCAFFOLDS[scaffolded.scaffold_id]
    out_root = _bp_Path(reg_entry["output_root"])

    for file_name, section_context in section_by_item.items():
        entry = scaffold_files.get(file_name)
        if entry is None:
            errors.append({
                "step": f"fill:{file_name}", "code": "not_found",
                "message": f"scaffolded file {file_name} not present",
            })
            continue

        if progress_cb is not None:
            await progress_cb({"chunk": {"file": file_name, "stage": "generating"}})

        scaffold_body = entry["content"]
        new_body = await _claude_fill_one(
            client, effort=effort, file_name=file_name,
            scaffold_body=scaffold_body, section_context=section_context,
            lint_feedback=None,
        )

        abs_path = out_root / entry["path"]
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(new_body, encoding="utf-8")

        if progress_cb is not None:
            await progress_cb({"chunk": {"file": file_name, "stage": "linting"}})
        lint1 = await _run_lint_on_file(abs_path)
        if lint1["errors"] == 0:
            entry["content"] = new_body
            continue

        # One retry with lint feedback
        if progress_cb is not None:
            await progress_cb({"chunk": {"file": file_name, "stage": "retrying"}})
        retry_body = await _claude_fill_one(
            client, effort=effort, file_name=file_name,
            scaffold_body=scaffold_body, section_context=section_context,
            lint_feedback="; ".join(lint1["details"][:5]),
        )
        abs_path.write_text(retry_body, encoding="utf-8")
        lint2 = await _run_lint_on_file(abs_path)
        if lint2["errors"] == 0:
            entry["content"] = retry_body
        else:
            # Give up: restore scaffold stub + record error
            abs_path.write_text(scaffold_body, encoding="utf-8")
            errors.append({
                "step": f"fill:{file_name}",
                "code": "lint_failed",
                "message": f"Lint failed twice; kept scaffold stub. Details: {lint2['details'][:3]}",
            })

    # Final whole-project lint
    final_lint = await _run_lint_on_dir(out_root / "src" / "deluge")

    return {
        "status": "partial_success" if errors else "success",
        "project_name": scaffolded.project_name,
        "files": list(scaffold_files.values()),
        "lint_result": final_lint,
        "errors": errors,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_build_pipeline.py -v`
Expected: PASS — 13/13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bridge/build_pipeline.py bridge/tests/test_build_pipeline.py
git commit -m "feat(bridge): fill pipeline with Claude per-file + single lint-retry"
```

---

### Task 5.5: Replace handle_build_project mock with mode dispatch

**Files:**
- Modify: `bridge/handlers.py`
- Create: `bridge/tests/test_handle_build_project.py`

- [ ] **Step 1: Write the failing test**

Create `bridge/tests/test_handle_build_project.py`:

```python
from unittest.mock import MagicMock

import pytest

from bridge import handlers


VALID_SECTIONS = [
    {"id": "forms", "title": "Forms", "items": ["F"]},
    {"id": "workflows", "title": "Workflows", "items": ["wf_one"]},
    {"id": "reports", "title": "Reports", "items": []},
    {"id": "approvals", "title": "Approvals", "items": []},
    {"id": "apis", "title": "APIs", "items": []},
]


@pytest.mark.asyncio
async def test_scaffold_mode_returns_files_and_scaffold_id(tmp_path, monkeypatch):
    monkeypatch.setattr("bridge.handlers._scaffold_output_root", lambda: tmp_path)

    chunks = []

    async def send(x):
        chunks.append(x)

    result = await handlers.handle_build_project(
        {"mode": "scaffold", "sections": VALID_SECTIONS, "project_name": "P"},
        send_fn=send,
    )
    assert result["status"] == "success"
    assert result["scaffold_id"].startswith("sc_")
    assert any(f["name"] == "wf_one.dg" for f in result["files"])
    assert chunks, "expected streaming progress chunks"


@pytest.mark.asyncio
async def test_fill_mode_requires_scaffold_id():
    async def send(x):
        pass

    result = await handlers.handle_build_project(
        {
            "mode": "fill",
            "sections": VALID_SECTIONS,
            "approved_scaffold": {"scaffold_id": "sc_unknown", "files": []},
        },
        send_fn=send,
    )
    assert result["status"] == "error"
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_fill_mode_returns_no_api_key_when_client_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("bridge.handlers._scaffold_output_root", lambda: tmp_path)

    async def send(x):
        pass

    # First scaffold so a valid scaffold_id exists
    scaffold_result = await handlers.handle_build_project(
        {"mode": "scaffold", "sections": VALID_SECTIONS, "project_name": "P"},
        send_fn=send,
    )
    sid = scaffold_result["scaffold_id"]

    monkeypatch.setattr("bridge.handlers.build_anthropic_client", lambda: None)
    result = await handlers.handle_build_project(
        {
            "mode": "fill",
            "sections": VALID_SECTIONS,
            "approved_scaffold": {"scaffold_id": sid, "files": scaffold_result["files"]},
        },
        send_fn=send,
    )
    assert result["code"] == "no_api_key"


@pytest.mark.asyncio
async def test_unknown_mode_returns_invalid_request():
    async def send(x):
        pass

    result = await handlers.handle_build_project(
        {"mode": "bogus", "sections": VALID_SECTIONS},
        send_fn=send,
    )
    assert result["code"] == "invalid_request"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_build_project.py -v`
Expected: FAIL — current `handle_build_project` is the mock with no `mode` support.

- [ ] **Step 3: Implement**

Add imports at top of `bridge/handlers.py`:

```python
from bridge.build_pipeline import (
    plan_from_sections,
    scaffold as _scaffold_pipeline,
    fill as _fill_pipeline,
    get_active_scaffold,
    ScaffoldResult,
)
```

Add a test-overridable helper near the top of `bridge/handlers.py`:

```python
def _scaffold_output_root() -> Path | None:
    """Hook for tests to redirect scaffold output. Returns None in prod (pipeline default)."""
    return None
```

Replace the existing `handle_build_project` function with:

```python
async def handle_build_project(data: dict, send_fn: SendFn) -> dict:
    """Build project in scaffold mode (deterministic) or fill mode (Claude)."""
    mode = data.get("mode", "scaffold")
    sections = data.get("sections", [])
    if mode not in {"scaffold", "fill"}:
        return build_error(f"Unknown mode: {mode!r}", "invalid_request")

    if mode == "scaffold":
        try:
            plan = plan_from_sections(sections, project_name=data.get("project_name"))
        except ValueError as exc:
            return build_error(str(exc), "invalid_request")

        await send_fn({"chunk": {"step": 1, "total": 3, "message": "Extracting generation plan..."}})
        override_root = _scaffold_output_root()
        await send_fn({"chunk": {"step": 2, "total": 3, "message": "Generating skeleton files..."}})
        scaffolded = await _scaffold_pipeline(plan, output_root=override_root)
        await send_fn({"chunk": {"step": 3, "total": 3, "message": "Linting scaffolded scripts..."}})

        return {
            "status": "success",
            "project_name": scaffolded.project_name,
            "scaffold_id": scaffolded.scaffold_id,
            "files": scaffolded.files,
            "lint_result": scaffolded.lint_result,
        }

    # mode == "fill"
    approved = data.get("approved_scaffold") or {}
    scaffold_id = approved.get("scaffold_id")
    files = approved.get("files") or []
    if not isinstance(scaffold_id, str) or not scaffold_id:
        return build_error("Missing approved_scaffold.scaffold_id", "invalid_request")

    plan = get_active_scaffold(scaffold_id)
    if plan is None:
        return {
            "status": "error",
            "code": "not_found",
            "error": f"Scaffold {scaffold_id} not found or expired.",
        }

    client = build_anthropic_client()
    if client is None:
        return no_api_key_error()

    scaffolded = ScaffoldResult(
        scaffold_id=scaffold_id,
        project_name=plan.project_name,
        files=files,
        lint_result={},
    )

    result = await _fill_pipeline(
        scaffolded,
        sections=sections,
        effort=data.get("effort") or "max",
        client=client,
        progress_cb=send_fn,
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/test_handle_build_project.py -v`
Expected: PASS — 4/4 tests pass.

Also run the full suite to ensure no regression: `cd C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS && python -m pytest bridge/tests/ -v`
Expected: all green (live-API tests skipped unless key is set).

- [ ] **Step 5: Commit**

```bash
git add bridge/handlers.py bridge/tests/test_handle_build_project.py
git commit -m "feat(bridge): replace handle_build_project mock with scaffold/fill dispatch"
```

---

## Self-review notes

### Pre-execution notes (from plan author)

- **Spec §6.4 step 2a / §11.4 assumption 4 — `forgeds.compiler.lint_rules` digest in fill prompts:** the module exposes an `ASTLinter` visitor class rather than an enumerable rule table, so a cheap text summary for prompt injection is not available. **Workaround for Task 5.4:** when building the per-file fill prompt, include the same CLAUDE.md Deluge conventions digest that `bridge/prompts.py` uses for `ai_chat` (via `build_ai_chat_system_prompt` or a shared constant). Do this inside the `_build_fill_prompt(...)` helper added in Task 5.4 Step 3 — prepend the digest as a "Rules the output must satisfy:" block before the skeleton snippet. No new module needed; re-use the existing digest string.
- **Spec §10 open question 3 (`parse_ds` graph summary):** Task 4.6 already wires graph build into `parse_ds`. If the engineer wants to surface counts in the `parse_ds` response (node count, edge count, external_refs count), extend the `handle_parse_ds` return dict in `bridge/handlers.py` — it is a 3-line addition and does not require a new task.

### To be filled by reviewer during plan execution

- Any task where a test had to be adjusted after hitting the real ForgeDS APIs (lexer edge cases, DSParser output shape surprises).
- Whether the AST walker fallback was exercised on real .dg scripts and, if so, which patterns the fallback needed to cover.
- Any spec §5.4 edge type that remained unemitted because its pre-conditions did not occur in the tiny fixture (e.g. `function_calls_function`, `field_lookup_target`, `report_source` — the tiny fixture has no reports or user-defined functions).
- Live-API test costs observed (target: under $0.10/run per spec §8.4).
- Follow-up items that should become new spec entries (e.g. `lint_rules` text-summary injection into fill prompts — deferred from this plan because `forgeds.compiler.lint_rules` is a set of ASTLinter methods, not an enumerable rule table).
