# ForgeDS Phase 2D.1 — `sidecar-bridge-route` Architecture Blueprint (Architect Twin B, Opus bisimulation)

**Date:** 2026-04-25 · **Branch:** `claude/forgeds-phase2d1-sidecar` · **Round:** 1

## 1. Module layout

```
src/forgeds/sidecar/                          [NEW package, stdlib-only]
  __init__.py                                 (public: SidecarServer, PortFile)
  __main__.py                                 (console-script entry)
  server.py                                   (ThreadingHTTPServer + handler)
  port_file.py                                (atomic write/read + shape validate)
  handlers.py                                 (per-endpoint callables; pure funcs)
  streaming.py                                (chunked NDJSON writer helper)
  _ndjson.py → re-export of src/forgeds/_shared/ndjson.py

src/forgeds/_shared/ndjson.py                 [NEW — extracted; see §8]
  (encode_frame, decode_stream, FrameError)

bridge/sidecar_client.py                      [NEW]
  (SidecarClient, HealthProbe, RestartBudget, HeartbeatTask)

bridge/server.py                              [MODIFY]
  L55–151  _handle_message:    insert forgeds:* branch after cancellation shortcut
  L143–150 exception tail:     route forgeds:* errors via v1 envelope path
  new L~40 module-scope:       _sidecar_clients: dict[str, ClientContext]
  new L~260 shutdown hook:     await sidecar_client.shutdown()

bridge/handlers.py                            [MODIFY]
  append: async def _handle_forgeds_message(msg, send_fn, client_ctx)
  reuse existing SendFn type (L21)

pyproject.toml                                [MODIFY]
  [project.scripts] add: forgeds-sidecar = "forgeds.sidecar.__main__:main"
  [project.optional-dependencies] add: bridge = ["websockets>=12"]

web/src/components/ide/DiagnosticsRenderer.tsx [NEW — inert stub]

tests/sidecar/                                [NEW dir]
  test_sidecar_lifecycle.py
  test_sidecar_port_file.py
  test_sidecar_restart_budget.py
  test_sidecar_ndjson_stream.py
  conftest.py                                 (free-port fixture, tmp-cwd fixture)

bridge/tests/test_forgeds_route.py            [NEW, lives in gap-close tree]
bridge/tests/test_deploy_intent_token.py      [NEW]
```

Rule registry addendum: CLAUDE.md rule-code registry table gets a new row `SDC###` | `forgeds.sidecar.*` + `bridge.sidecar_client` | "Sidecar process / bridge-to-sidecar transport diagnostics". Modified by the plan phase, not this blueprint.

## 2. Sidecar module design

### `server.py`

Class `SidecarServer` wraps `http.server.ThreadingHTTPServer`. Constructor takes `(port_range: tuple[int,int] = (9877, 9885), project_root: Path)`. Instance method `.bind()` iterates the range, catches `OSError` where `err.errno == errno.EADDRINUSE` (Windows 10048, Linux 98), returns on first success, raises `SidecarBindError` after exhaustion. Does **not** set `allow_reuse_address` (per research finding #3 — masks probes).

Handler class `SidecarHandler(BaseHTTPRequestHandler)` dispatches via a class-level `ROUTES: dict[tuple[str,str], Callable]`:

| Method | Path | Handler | Streaming |
|---|---|---|---|
| GET | `/health` | `handle_health` | no |
| POST | `/shutdown` | `handle_shutdown` | no |
| POST | `/forgeds/lint` | `handle_lint` | no |
| POST | `/forgeds/scaffold` | `handle_scaffold` | no |
| POST | `/forgeds/fs/read` | `handle_fs_read` | no |
| POST | `/forgeds/bundle` | `handle_bundle` | **yes** |
| POST | `/forgeds/verify` | `handle_verify` | **yes** |

Every response carries `X-Forgeds-Sidecar-Version: 1` (frozen seam). `do_GET` / `do_POST` both look up `ROUTES[(method, path)]`, 404 otherwise. Request body read via `int(self.headers["Content-Length"])` then `self.rfile.read(n).decode("utf-8")` — **explicit UTF-8** (never system locale).

Streaming handlers receive a `ChunkedResponse` helper from `streaming.py`: sends `200 OK`, `Content-Type: application/x-ndjson`, `Transfer-Encoding: chunked`, then for each chunk writes `hex(len)\r\n`, payload bytes, `\r\n`, and — per research finding #1 — calls `self.wfile.flush()` after **every** line. Terminator chunk `0\r\n\r\n` closes the transfer. In-band errors flow through the same writer as `{"type":"error",...}` frames and do NOT bypass the `stream_end` terminator.

`handle_shutdown` (research finding #2): write response body, `self.wfile.flush()`, then `threading.Thread(target=self.server.shutdown, daemon=True).start()`. Never call `server.shutdown()` from the handler thread.

### `port_file.py`

Public functions:
- `write_port_file(root: Path, port: int, pid: int) -> Path` — serialize `{"port":p,"pid":pid,"started_at":datetime.now(timezone.utc).isoformat()}` using `json.dumps(..., ensure_ascii=False)`, write to `root/.forgeds-sidecar.port.tmp`, `os.replace()` to final name. Catch `OSError` with `err.errno in (errno.EXDEV, 18)` → copyfile-then-unlink fallback. Mirrors `src/forgeds/widgets/spec_loader.py:247–325` (the sole canonical pattern per research finding #4).
- `read_port_file(root: Path) -> PortRecord | None` — returns dataclass with port/pid/started_at; missing file → None; malformed JSON → None (caller treats as stale).
- `validate_health_shape(body: dict) -> bool` — checks `body.get("tool") == "forgeds-sidecar"` AND `body.get("version") == "1"`.

### `__main__.py`

```
parse_args()  -> --port-range, --project-root, --log-level
resolve project_root (default: cwd)
server = SidecarServer(...).bind()
write_port_file(project_root, server.port, os.getpid())
register atexit: best-effort port-file unlink
server.serve_forever()
```

Logs to stderr via `logging.basicConfig(stream=sys.stderr)` so bridge can capture. No third-party deps.

### `handlers.py`

Pure handler functions for each endpoint. `handle_lint(payload)` wraps `forgeds.core.lint_deluge.run` and serializes via `forgeds._shared.envelope.to_json_v1("forgeds-lint", diagnostics)` (research finding #11). Streaming handlers (`handle_bundle`, `handle_verify`) yield frames — they're generator functions; `ChunkedResponse` consumes the generator.

## 3. Bridge extensions

### `bridge/sidecar_client.py`

```python
class SidecarClient:
    def __init__(self, project_root: Path, loop: asyncio.AbstractEventLoop,
                 broadcast: Callable[[dict], Awaitable[None]]): ...

    async def ensure_running(self) -> int:
        # 1. read_port_file -> if present, GET /health (500ms timeout)
        # 2. validate_health_shape(body) AND response status 200
        # 3. success -> return port  (research A1: HTTP is authoritative, PID informational)
        # 4. failure -> self._spawn()  -> overwrite port-file via new child
        # 5. budget check BEFORE spawn

    async def invoke(self, path: str, payload: dict) -> dict: ...      # req/res
    async def stream(self, path: str, payload: dict,
                     send_fn: SendFn) -> None:                          # NDJSON

    async def shutdown(self) -> None:      # POST /shutdown, 2s grace, then kill
```

Health probe semantics (A1): `aiohttp`-free — use `asyncio.wait_for(loop.run_in_executor(None, urllib_get), 0.5)` with `urllib.request`. Stdlib-only. Shape-validate before treating port as live.

`stream()` issues `POST path` with `Accept: application/x-ndjson`, reads `response.fp` line-by-line, and for each line:
1. `json.loads(line)` → on `JSONDecodeError` emit `SDC006` diagnostic via `send_fn` and abort stream.
2. Frame `type == "chunk"` or `type == "error"` → forward as `{"id":req_id, "type":"forgeds:cli:bundle:stream", "data":<frame>}`.
3. Frame `type == "stream_end"` → emit `{"id":req_id, "type":"forgeds:cli:bundle:complete", ...}` and exit loop.
4. Connection closed before `stream_end` → `SDC006`.

**Restart budget** (state machine):
```
RestartBudget(max=3, window_sec=300)
  .record() -> RestartResult.OK | EXCEEDED
  timestamps deque; expire > window; len >= max at next .record() -> EXCEEDED
```
On `OK` → broadcast `SDC003` (warning). On `EXCEEDED` → broadcast `SDC004` (error) and set `self._halted = True`; all subsequent `ensure_running()` raise `SidecarHalted`.

**Heartbeat** (research finding #5): `asyncio.create_task(self._heartbeat_loop())` — every 30s issues `GET /health`; three consecutive misses → `SDC005`, mark sidecar dead (clear cached port), next `ensure_running()` respawns.

### `bridge/server.py` integration

Module-scope registry (near imports, ~L40):
```python
_sidecar_clients: dict[str, ClientContext] = {}   # per research #8 + #13
_sidecar_client: SidecarClient | None = None
```

`_handle_message` (L55–151) edits:

| Anchor | Edit |
|---|---|
| After cancellation shortcut (gap-close L82–90) | **Insert**: `if msg_type.startswith("forgeds:"): return await _handle_forgeds_message(msg, send_fn, client_ctx)` |
| Exception tail (L143–150) | Branch: if original `msg_type` starts with `forgeds:`, log via `bridge.enrichment.log_error` and emit v1-envelope diagnostic; else preserve existing generic error |

Router placement is **before** the 13 flat `elif`s and **after** the cancellation shortcut — cancellation is universal; `forgeds:*` is its own namespace and should fail fast without scanning the legacy chain (research finding #6).

Graceful shutdown path (~L260): `await _sidecar_client.shutdown()` before the WS server closes; port-file removed by sidecar `atexit`.

### `bridge/handlers.py`

New function:

```python
async def _handle_forgeds_message(msg: dict, send_fn: SendFn,
                                   client_ctx: ClientContext) -> None:
    msg_type = msg["type"]
    req_id = msg.get("id")
    data = msg.get("data", {})

    dispatch = {
        "forgeds:cli:lint":     ("POST", "/forgeds/lint",     False),
        "forgeds:cli:scaffold": ("POST", "/forgeds/scaffold", False),
        "forgeds:cli:bundle":   ("POST", "/forgeds/bundle",   True),
        "forgeds:cli:verify":   ("POST", "/forgeds/verify",   True),
        "forgeds:fs:read":      ("POST", "/forgeds/fs/read",  False),
        "forgeds:cli:deploy":   _deploy_gate,   # callable, see below
    }
    entry = dispatch.get(msg_type)
    if entry is None:
        return await send_fn(sdc010(msg_type, req_id))     # SDC010 warning

    method, path, streaming = entry
    client = get_sidecar_client()
    await client.ensure_running()    # may raise SidecarHalted -> SDC004 already broadcast
    if streaming:
        await client.stream(path, data, wrap_send(send_fn, req_id))
    else:
        result = await client.invoke(path, data)
        await send_fn({"id": req_id, "type": f"{msg_type}:result", "data": result})
```

`_deploy_gate` checks `data.get("deploy_intent_token")` present and non-empty; missing/empty → emit `SDC020`. 2D.1 does not yet verify against a consumed set (that's 2D.4) but the call site is wired.

## 4. Wire formats

### Sidecar HTTP

Request (`POST /forgeds/lint`):
```json
{"target": "src/deluge/foo.dg", "options": {"strict": true}}
```
Response (non-streaming):
```json
{"tool":"forgeds-lint","version":"1","diagnostics":[...],"exit_code":0}
```
Health:
```json
{"tool":"forgeds-sidecar","version":"1","status":"ok","pid":12345,"uptime_sec":42}
```

### NDJSON frames (framing seam FROZEN)

```
{"type":"chunk","seq":0,"data":{...tool-specific payload...}}
{"type":"chunk","seq":1,"data":{...}}
{"type":"error","seq":2,"diagnostic":{...v1-envelope-single-diagnostic...}}
{"type":"stream_end","seq":3,"exit_code":0,"duration_ms":1234}
```
Every frame has `type` + `seq` (monotonic). `stream_end` always terminates (per B1); absence = framing failure = SDC006.

### Bridge WS

Inbound renderer → bridge:
```json
{"id":"r-88","type":"forgeds:cli:lint","data":{"target":"..."}}
{"id":"r-89","type":"forgeds:cli:deploy","data":{"widget":"foo","deploy_intent_token":"dit-9f3c..."}}
```
Outbound streaming:
```json
{"id":"r-90","type":"forgeds:cli:bundle:stream","data":{"type":"chunk","seq":0,"data":{...}}}
{"id":"r-90","type":"forgeds:cli:bundle:complete","data":{"exit_code":0}}
```
Broadcast:
```json
{"id":null,"type":"forgeds:diagnostics:broadcast","data":{"tool":"forgeds-sidecar","version":"1","diagnostics":[{"rule":"SDC003","severity":"warning",...}]}}
```

### Port-file
```json
{"port":9877,"pid":48210,"started_at":"2026-04-24T14:22:01.123456+00:00"}
```

## 5. Lifecycle diagrams

**Happy path (first request)**
```
Renderer  Bridge           SidecarClient   Sidecar(proc)
  |---forgeds:cli:lint--->|                      (not running)
  |                       |--read port-file---> (none)
  |                       |--spawn-------------> python -m forgeds.sidecar
  |                       |                      binds :9877, writes port-file
  |                       |--GET /health-------->|
  |                       |<--200 {tool,ver:1}---|
  |                       |--POST /forgeds/lint->|
  |                       |<--200 {v1 envelope}--|
  |<--forgeds:cli:lint:result---|
```

**Crash recovery**
```
req1 -> spawn -> crash -> budget.record()=OK  -> broadcast SDC003 -> respawn
req2 -> health FAIL -> budget.record()=OK      -> broadcast SDC003 -> respawn
req3 -> health FAIL -> budget.record()=OK      -> broadcast SDC003 -> respawn
req4 -> health FAIL -> budget.record()=EXCEEDED-> broadcast SDC004 -> halt
         subsequent forgeds:* -> SDC001 direct reply (sidecar halted)
```

**Two-window race**
```
Window A bridge: spawn sidecar, writes port-file {port:9877,pid:A}
Window B bridge: reads port-file, GET /health (200) -> reuse, no spawn
```
If A's sidecar crashes while B is mid-call: B gets connection error → B respawns → B overwrites port-file with its own PID. A's next call reads the file, health-probes, succeeds against B's sidecar. Port-file is shared session state; PID is informational (A1).

**Heartbeat miss**
```
t=0    heartbeat OK
t=30   heartbeat timeout (1)
t=60   heartbeat timeout (2)
t=90   heartbeat timeout (3) -> SDC005 broadcast, cached port cleared
next forgeds:* -> ensure_running() -> read port-file -> /health FAIL -> respawn
```

## 6. Error & diagnostic flow

| Code | Emitted at (file:~line) | Trigger | Payload | Consumer |
|---|---|---|---|---|
| SDC001 | `bridge/sidecar_client.py` `ensure_running` | Health probe 5xx/connrefused after spawn | v1 envelope, rule SDC001 | Renderer shows connection error |
| SDC002 | `bridge/sidecar_client.py` `ensure_running` | Port-file present, `/health` returns non-sidecar shape OR stale | v1 envelope with port/pid in `meta` | Bridge overwrites, respawns |
| SDC003 | `RestartBudget.record()` OK branch | 1st/2nd/3rd restart in 5-min window | v1 envelope + `restart_count` | Broadcast to all `_sidecar_clients` |
| SDC004 | `RestartBudget.record()` EXCEEDED | 4th+ restart in window | v1 envelope + timestamps list | Broadcast; bridge halts sidecar use |
| SDC005 | `HeartbeatTask._on_miss` | 3 consecutive 30s misses | v1 envelope + `missed_count:3` | Bridge clears cached port |
| SDC006 | `SidecarClient.stream` JSON decode / EOF-before-stream_end | NDJSON framing failure | v1 envelope + `raw_line` (truncated 200 chars) | In-band via same `send_fn` |
| SDC010 | `_handle_forgeds_message` unknown-type branch | Renderer sent `forgeds:unknown:foo` | v1 envelope + `received_type` | Reply to sender only, not broadcast |
| SDC020 | `_deploy_gate` | Missing/empty `deploy_intent_token` | v1 envelope + `request_id` | Reply to sender; do NOT proxy to sidecar |

Sidecar in-band `error` frames (tool-level failures) flow: sidecar emits `{"type":"error","diagnostic":{...}}` → `SidecarClient.stream` forwards as `{"type":"forgeds:cli:bundle:stream","data":{"type":"error",...}}` → renderer's `DiagnosticsRenderer.tsx` consumes the `diagnostic` key. Framing-level failures (SDC006) are bridge-side and do not originate from sidecar frames.

## 7. Test strategy

Location split: sidecar tests live in `tests/sidecar/` (import-only); bridge round-trip tests live in `bridge/tests/` (pytest-asyncio, coexists with gap-close infra per #13).

| File | Test name | Purpose |
|---|---|---|
| `tests/sidecar/test_sidecar_lifecycle.py` | `test_health_endpoint_shape` | GET /health returns `{tool:"forgeds-sidecar",version:"1"}` |
| | `test_shutdown_endpoint_graceful` | POST /shutdown returns 200 then process exits within 2s |
| | `test_version_header_present` | `X-Forgeds-Sidecar-Version:1` on every response |
| `tests/sidecar/test_sidecar_port_file.py` | `test_port_file_rewrite` | Second sidecar on same root overwrites port-file atomically |
| | `test_port_file_exdev_fallback` | Simulate `EXDEV`, verify copy-then-unlink fallback |
| | `test_port_file_malformed_json_treated_stale` | Corrupted file → `read_port_file` returns None |
| `tests/sidecar/test_sidecar_ndjson_stream.py` | `test_stream_end_terminates` | Bundle streaming produces final `stream_end` frame |
| | `test_inband_error_frame_shape` | Tool failure → `{"type":"error","diagnostic":{...}}` frame |
| | `test_windows_flush_emits_chunks_eagerly` | Subprocess consumer sees chunks before stream end (research #1) |
| `tests/sidecar/test_sidecar_restart_budget.py` | `test_restart_budget_ok_then_exceeded` | 3 restarts → SDC003 ×3; 4th → SDC004 and halt |
| | `test_restart_window_expiry` | Restart > 300s later → counter resets |
| `bridge/tests/test_forgeds_route.py` | `test_forgeds_cli_lint_roundtrip` | WS msg → sidecar invoked → v1 envelope returned |
| | `test_forgeds_cli_bundle_streaming_roundtrip` | Streaming WS flow; assert chunk+stream_end pairing |
| | `test_unknown_forgeds_type_emits_SDC010` | Unknown `forgeds:*` → SDC010 warning, no crash |
| | `test_bridge_strips_auth_headers` | Placeholder (2D.4 expands); asserts no `Authorization` echoed |
| `bridge/tests/test_deploy_intent_token.py` | `test_deploy_intent_token_required` | `forgeds:cli:deploy` without token → SDC020, not proxied |
| | `test_deploy_intent_token_bound_to_request_id` | Token field present on outbound deploy payload; request_id matches |

Fixtures (`tests/sidecar/conftest.py`):
- `free_port` — binds port 0, closes, returns number (race-prone but acceptable for isolated tests).
- `tmp_project_root` — `tmp_path` cast with dummy `forgeds.yaml`.
- `sidecar_process` — context-managed subprocess; yields `(port, pid, project_root)`; terminates on exit.
- `mock_sidecar` (bridge-side) — `aiohttp.pytest_plugin` avoided; use `http.server` in thread for genuine integration.

## 8. Gotchas & mitigations (Windows-focused)

| Gotcha | Mitigation |
|---|---|
| Chunks batch invisibly on Windows stdio | `wfile.flush()` after every NDJSON line (research #1). Unit-tested. |
| Cross-volume rename (EXDEV) on project roots on different drives | Copy-then-unlink fallback in `port_file.write_port_file`, mirroring `widgets/spec_loader.py:247–325`. |
| System-locale bytes on Python 3.10 Windows default | Every `decode()`/`encode()` call passes `"utf-8"` explicitly; `open()` uses `encoding="utf-8"`. |
| `errno.EADDRINUSE` value differs (98 Linux / 10048 Windows) | Use `errno.EADDRINUSE` constant, never the literal. |
| `allow_reuse_address=True` masks in-use probe | Do NOT set it (research #3). |
| `ThreadingHTTPServer.shutdown()` from handler thread deadlocks | Spawn daemon thread in shutdown handler (research #2). |
| `subprocess.Popen` spawning sidecar inherits stdio → blocks on Windows | Redirect stdout/stderr to PIPE or DEVNULL in `SidecarClient._spawn`. |
| Port 9877 occupied by unrelated tool | Probe 9877–9885, propose moving to user-addressable config if all fail (2D.10 scope). |
| Timezone-naive timestamps in port-file | Always use `datetime.now(timezone.utc).isoformat()`. |

## 9. Composability hooks (gap-close merge plan)

**Router placement**: `forgeds:*` branch goes **after** the gap-close cancellation shortcut (L82–90) and **before** the 13 flat `elif`s. Reason: cancellation is cross-cutting and must apply to in-flight `forgeds:*` streams too; placing `forgeds:*` before the flat chain avoids scanning 13 unrelated types per message. This satisfies both branches.

**`_sidecar_clients` registry**: module-scope dict near top of `bridge/server.py` (~L40), named explicitly `_sidecar_clients` (not `_clients`, not `_authenticated_clients` — per research #13 recommendation). Any future chat-client registry from gap-close can coexist under a distinct name. Entries populated on WS connect (where gap-close adds session binding) and cleaned on disconnect.

**`handle_ai_chat` signature**: respected as-is; gap-close's `send_fn: SendFn | None = None` optional param is not touched by this phase. 2D.1 handlers do not call into `handle_ai_chat`.

**Namespace collision avoidance**: gap-close introduces `bridge/session_store.py` for conversation history. Our future consumed-deploy-intent set (2D.4 scope, not 2D.1) is reserved as `bridge/deploy_intent_ledger.py` — distinct file, distinct name. 2D.1 creates no file that collides with gap-close.

**Dependencies**: `bridge/requirements.txt` additions = **none** for 2D.1 (stdlib-only via `urllib.request` + `asyncio`). `pyproject.toml` gets `[project.optional-dependencies] bridge = ["websockets>=12"]` to resolve the pre-existing debt noted in research #12, with CLAUDE.md stating sidecar itself stays stdlib-only. Merge order with gap-close: non-conflicting additions; CI runs both test trees.

## 10. Open questions / risks for Phase 5 (spec) + Phase 6 (plan)

1. **Port-range exhaustion UX** — if 9877–9885 all fail, do we surface `SDC002` + exit, or read a user-configured range from `forgeds.yaml`? Plan phase decide.
2. **Multi-root concurrency** — two IDE windows on *different* project roots each write their own port-file; is there a discovery collision if roots are nested? Need simulation.
3. **Sidecar orphan on bridge hard-kill** — `atexit` doesn't fire on SIGKILL. Do we add a PID-age watchdog on next bridge start, or accept orphan until reboot? Affects A1's "PID informational" posture.
4. **`FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY` interaction with SDC020** — when spike gate is bypassed in pytest, is intent-token still required? Recommend: yes (orthogonal concerns). Needs spec call-out.
5. **NDJSON back-pressure** — if renderer is slow, sidecar streams buffer in bridge memory. Cap chunk-buffer size and SDC-diagnose if exceeded? Leave to 2D.5?
6. **Heartbeat vs request coalescing** — if a long-running `/forgeds/bundle` is mid-stream, does heartbeat ping on a separate connection count? Confirm `http.server` handles concurrent connections (it does via threading, but verify under load).
7. **`_generated/` typegen interaction** — if 2D.1 lint hits a widget referencing a stale `_generated/` file, does the sidecar detect it or punt to `forgeds-status`? Out of scope but plan phase should annotate.
