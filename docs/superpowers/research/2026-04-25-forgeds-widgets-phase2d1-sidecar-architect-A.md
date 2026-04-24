# ForgeDS Phase 2D.1 — `sidecar-bridge-route` Implementation Blueprint (Architect Twin A, Opus bisimulation)

**Date:** 2026-04-25 · **Branch:** `claude/forgeds-phase2d1-sidecar` · **Round:** 1

## 1. Module layout

```
ForgeDS/
├── src/forgeds/
│   ├── sidecar/                              [NEW PACKAGE]
│   │   ├── __init__.py                       [NEW] package marker; exports VERSION="1"
│   │   ├── __main__.py                       [NEW] CLI entry; argparse; startup orchestration
│   │   ├── server.py                         [NEW] ThreadingHTTPServer + BaseHTTPRequestHandler
│   │   ├── port_file.py                      [NEW] atomic write/read/validate of .forgeds-sidecar.port
│   │   ├── handlers.py                       [NEW] per-endpoint dispatch tables (lint/scaffold/bundle/verify/fs-read)
│   │   ├── streaming.py                      [NEW] chunked-HTTP NDJSON writer with mandatory flush()
│   │   └── errors.py                         [NEW] in-band error-frame builder using _shared.envelope
│   ├── _shared/
│   │   └── ndjson.py                         [NEW] framing helpers: encode_frame, parse_frame, FRAME_TYPES
│   └── widgets/
│       └── (unchanged — spec_loader atomic-write pattern referenced only)
├── bridge/
│   ├── server.py                             [MODIFY] lines 55-151 (+ new _sidecar_clients registry near 30)
│   ├── handlers.py                           [MODIFY] append _handle_forgeds_message + helpers (~line 200+)
│   ├── sidecar_client.py                     [NEW] SidecarClient: spawn, probe, proxy, heartbeat, restart FSM
│   ├── requirements.txt                      [MODIFY] no new deps (sidecar is stdlib)
│   └── tests/
│       ├── test_sidecar_client.py            [NEW] unit tests for SidecarClient
│       ├── test_forgeds_router.py            [NEW] bridge-level routing tests
│       └── conftest.py                       [MODIFY if exists, else NEW] add sidecar_fixture
├── tests/sidecar/                            [NEW DIR]
│   ├── __init__.py                           [NEW]
│   ├── test_sidecar_lifecycle.py             [NEW]
│   ├── test_sidecar_port_file_rewrite.py     [NEW]
│   ├── test_sidecar_restart_budget.py        [NEW]
│   ├── test_sidecar_streaming.py             [NEW]
│   ├── test_sidecar_fs_read.py               [NEW]
│   └── test_deploy_intent_token_skeleton.py  [NEW]
├── web/src/components/ide/
│   └── DiagnosticsRenderer.tsx               [NEW] inert stub; TS interface only
└── pyproject.toml                            [MODIFY] [project.scripts] append forgeds-sidecar
```

**Modification line-ranges:**

| File | Lines | Change |
|---|---|---|
| `bridge/server.py` | ~30 (top of class) | add `self._sidecar_clients: dict[str, ClientContext]` and `self._sidecar_client: SidecarClient \| None = None` |
| `bridge/server.py` | 82-90 | PRESERVE gap-close cancellation shortcut; do not insert router here |
| `bridge/server.py` | 143-150 (generic exception handler) | keep for non-forgeds; forgeds path owns its try/except |
| `bridge/server.py` | end of `_handle_message` flat elif chain (after line 151) | append `elif msg_type.startswith("forgeds:"): await _handle_forgeds_message(...)` |
| `bridge/handlers.py` | end of file | append `_handle_forgeds_message`, `_mint_deploy_intent_token`, `_broadcast_sidecar_diagnostic` |
| `pyproject.toml` | `[project.scripts]` block | `forgeds-sidecar = "forgeds.sidecar.__main__:main"` |

## 2. Sidecar module design

### `server.py`
Single class `SidecarHTTPServer(ThreadingHTTPServer)` holding `self.shutdown_event: threading.Event` and `self.deploy_intent_override_allowed: bool` (test-only).

Handler class `SidecarHandler(BaseHTTPRequestHandler)` overrides `do_GET` / `do_POST` and dispatches via two dict literals keyed by path:

```
ROUTES_GET  = {"/health": _h_health}
ROUTES_POST = {
  "/shutdown":         _h_shutdown,
  "/forgeds/lint":     _h_lint,          # req/res
  "/forgeds/scaffold": _h_scaffold,      # req/res
  "/forgeds/fs/read":  _h_fs_read,       # req/res
  "/forgeds/bundle":   _h_bundle,        # STREAM
  "/forgeds/verify":   _h_verify,        # STREAM
}
```

Every response sets `X-Forgeds-Sidecar-Version: 1` (frozen seam). Req/res endpoints: `Content-Type: application/json`, `Content-Length` computed. Streaming endpoints: `Transfer-Encoding: chunked`, hand off to `streaming.StreamingWriter`.

`_h_shutdown`: reply 200 OK with `{"ok":true}`, then spawn `threading.Thread(target=server.shutdown, daemon=True).start()` — avoids handler-thread deadlock (research finding #2).

Override `log_message` to no-op so stdlib BaseHTTPRequestHandler doesn't pollute stderr; sidecar owns its logging format.

### `streaming.py`
Class `StreamingWriter(wfile, handler)`:

- `write_frame(frame: dict)` — `line = json.dumps(frame, ensure_ascii=False, separators=(",",":")).encode("utf-8") + b"\n"`; emits chunk in HTTP/1.1 chunked form (`f"{len(line):X}\r\n".encode() + line + b"\r\n"`); then `wfile.flush()` — **mandatory on Windows** (research #1).
- `write_stream_end(ok: bool, counts: dict \| None)` — emits `{"type":"stream_end","ok":ok,"counts":counts or {}}` then terminator `b"0\r\n\r\n"` and flush.
- Context-manager semantics: `__exit__` with exception -> emit `{"type":"error","diagnostic":<v1-envelope>}` then `stream_end(ok=False)`.

### `port_file.py`
- `PORT_FILE_NAME = ".forgeds-sidecar.port"`
- `write_port_file(root: Path, port: int, pid: int) -> None`: mirrors `src/forgeds/widgets/spec_loader.py:247-325` atomic pattern — `tmp = root / f".forgeds-sidecar.port.tmp.{os.getpid()}"`, json dump UTF-8, `os.replace(tmp, target)`; `except OSError as e: if e.errno == errno.EXDEV: shutil.copyfile + os.remove(tmp)`.
- `read_port_file(root: Path) -> dict | None`: shape-validate keys `{port:int, pid:int, started_at:str}`; returns None on missing / bad-shape.
- `remove_port_file(root: Path) -> None`: best-effort unlink, swallow FileNotFoundError.

### `handlers.py` (sidecar-side, not bridge)
Thin functions: each reads JSON body (`int(self.headers["Content-Length"])`, `rfile.read(n)`, `json.loads`), calls existing ForgeDS Python API (`forgeds.core.lint_deluge.lint_files(...)`, `forgeds.widgets.scaffold_widget.scaffold_from_spec(...)`, `forgeds.widgets.bundle_widget.bundle_stream(...)`), wraps with `envelope.to_json_v1(tool, diags)`. Bundle/verify are generator-based and call `streaming.write_frame` per diagnostic.

### `__main__.py`
`main()`: argparse `--port` (default 9877), `--root` (default cwd), `--probe-range` (default 9878-9885). Probe loop: attempt bind, catch `OSError` where `errno.errno == errno.EADDRINUSE` (Windows 10048), retry with next port, give up after range exhausted and exit 3. Write port-file. Register `atexit` to remove port-file. Start server with `server.serve_forever()`. On KeyboardInterrupt: `server.shutdown()`.

`_shared/ndjson.py` (extraction justified — research #10): `encode_frame(obj) -> bytes`, `parse_line(line: bytes) -> dict`, constants `FRAME_CHUNK`, `FRAME_ERROR`, `FRAME_STREAM_END`. Reused by bridge client on read side.

Zero third-party imports. Stdlib only: `http.server`, `threading`, `json`, `os`, `errno`, `shutil`, `argparse`, `socket`, `atexit`, `time`, `datetime`, `pathlib`.

## 3. Bridge extensions

### `bridge/sidecar_client.py` (new)

```
class ClientContext:        # per-WS-connection row in registry
    ws: WebSocketServerProtocol
    authenticated: bool
    connected_at: datetime

class RestartBudget:
    MAX = 3                 # per 5-minute window
    WINDOW_SEC = 300
    _timestamps: deque[float]
    def record_and_check() -> Literal["ok","warn","exceeded"]

class SidecarClient:
    ROOT: Path
    PROBE_TIMEOUT_MS = 500
    HEARTBEAT_INTERVAL_SEC = 30
    HEARTBEAT_MAX_MISS = 3

    async def ensure_running() -> None
        # 1. read port-file; if present, GET /health with 500ms timeout
        # 2. validate body shape: tool=="forgeds-sidecar", version=="1"
        # 3. hit -> done. miss -> _spawn_fresh()
    async def _spawn_fresh() -> None
        # fork subprocess.Popen([sys.executable,"-m","forgeds.sidecar",...])
        # poll port-file for up to 3s; GET /health; on success -> start_heartbeat
        # on budget.record_and_check() result:
        #   "warn"     -> broadcast SDC003
        #   "exceeded" -> broadcast SDC004; raise SidecarBudgetExceeded
    async def invoke(path: str, body: dict) -> dict
        # req/res; raises SidecarUnreachable (SDC001 upstream)
    async def invoke_stream(path: str, body: dict, send_fn: SendFn, request_id: str)
        # opens HTTP, iterates wfile line-by-line via asyncio-compatible wrapper
        # each line -> json.loads -> translate to WS `forgeds:stream` event via send_fn
        # detect premature close (no stream_end frame observed) -> emit SDC006
    async def shutdown() -> None
        # POST /shutdown (best effort, 1s timeout)
    def _start_heartbeat() -> None  # threading.Timer re-sched; 3 miss -> mark dead
```

Heartbeat pattern: `threading.Timer(30, self._heartbeat_tick)`; `_heartbeat_tick` does GET /health with 1s timeout, increments `_miss_count` on failure, zero on success; at 3 → schedule async `_mark_dead()` which broadcasts SDC005 and nulls the process handle so next invoke triggers respawn.

### `bridge/server.py` edits

1. **Top of `BridgeServer.__init__`** (~line 30): add `self._sidecar_clients: dict[str, ClientContext] = {}` and `self._sidecar_client: SidecarClient | None = None` and `self._deploy_intent_ledger: set[str] = set()` (name reserved; consumed-verify lands 2D.4).
2. **WS connect handler**: on successful upgrade/auth, `self._sidecar_clients[connection_id] = ClientContext(ws, authenticated=True, connected_at=datetime.utcnow())`. On disconnect: `del`.
3. **`_handle_message` dispatch** (after line 151, AFTER the flat 13 elifs): append
   ```
   elif msg_type.startswith("forgeds:"):
       await _handle_forgeds_message(self, websocket, connection_id, msg, send_fn)
   else:
       await send_fn({"type":"error","data":{"message":f"unknown type {msg_type}"}})
   ```
   **Placement choice**: AFTER the 13 flat elifs, BEFORE the final unknown-fallthrough. Rationale: keeps gap-close cancellation shortcut at 82-90 untouched; `forgeds:*` types are brand-new so there's no legacy collision; putting them last preserves the readability of the current chain for reviewers merging gap-close.
4. **Broadcast helper** on BridgeServer:
   ```
   async def broadcast_sidecar_diagnostic(diagnostic_dict):
       envelope = to_json_v1("forgeds-sidecar", [diagnostic_dict])
       msg = {"id": None, "type": "forgeds:diagnostics:broadcast", "data": envelope}
       for ctx in list(self._sidecar_clients.values()):
           if ctx.authenticated:
               try: await ctx.ws.send(json.dumps(msg))
               except: pass   # drop dead sockets; disconnect handler will clean
   ```

### `bridge/handlers.py` additions

```
async def _handle_forgeds_message(server, ws, conn_id, msg, send_fn):
    msg_type = msg["type"]; req_id = msg.get("id"); data = msg.get("data",{})
    try:
        await server._sidecar_client_lazy_init()
        if msg_type == "forgeds:cli:lint":
            res = await server._sidecar_client.invoke("/forgeds/lint", data)
            await send_fn({"id":req_id,"type":"forgeds:cli:lint:result","data":res})
        elif msg_type == "forgeds:cli:scaffold":  ...
        elif msg_type == "forgeds:cli:bundle":
            await server._sidecar_client.invoke_stream("/forgeds/bundle", data, send_fn, req_id)
        elif msg_type == "forgeds:cli:verify":    ...  # stream
        elif msg_type == "forgeds:fs:read":       ...  # req/res; 100KB cap enforced server-side too
        elif msg_type == "forgeds:cli:deploy":
            token = data.get("deploy_intent_token")
            if not token or token in server._deploy_intent_ledger:
                # SDC020
                await _emit_diag(send_fn, req_id, "SDC020", "deploy-intent-token invalid/replayed")
                return
            server._deploy_intent_ledger.add(token)   # 2D.4 will wire consume + expiry
            res = await server._sidecar_client.invoke("/forgeds/deploy", data)
            await send_fn(...)
        else:
            # SDC010
            await _emit_diag(send_fn, req_id, "SDC010", f"unknown forgeds type: {msg_type}")
    except SidecarUnreachable:
        await _emit_diag(send_fn, req_id, "SDC001", "sidecar unreachable")
    except SidecarBudgetExceeded:
        pass   # SDC004 already broadcast
    except Exception as e:
        bridge.enrichment.log_error(e, context={"type": msg_type, "id": req_id})
        await _emit_diag(send_fn, req_id, "SDC-internal", "internal bridge error")
```

Error contract: never leak exception repr to WS; always land as v1-envelope diagnostic via `to_json_v1("forgeds-bridge", [...])`.

## 4. Wire formats

### Sidecar HTTP

**`GET /health`** (no body) → `200` + `{"tool":"forgeds-sidecar","version":"1","status":"ok","pid":12345,"uptime_sec":42}`

**`POST /forgeds/lint`** req `{"paths":["src/deluge/..."], "rules":["DG001",...] | null}` → res = v1 envelope `{"version":"1","tool":"forgeds-lint","diagnostics":[...],"summary":{...}}`.

**`POST /forgeds/scaffold`** req `{"spec_path":"widgets/foo/widget-spec.yaml","force":false}` → v1 envelope tool=`forgeds-scaffold-widget`.

**`POST /forgeds/fs/read`** req `{"path":"rel/or/abs","max_bytes":102400}` → res `{"ok":true,"path":"...","bytes":12345,"encoding":"utf-8","content":"..."}` OR truncated `{"ok":true,"path":"...","bytes":200000,"truncated":true,"summary":{"head":"first 2KB...","tail":"last 2KB..."}}` OR refusal `{"ok":false,"reason":"binary"}`.

**Streaming (`/forgeds/bundle`, `/forgeds/verify`)** — `Transfer-Encoding: chunked`; each chunk = one JSON line + `\n`:

```
{"type":"chunk","diagnostic":{"rule":"BND003","severity":"warning","message":"...","file":"..."}}
{"type":"chunk","progress":{"stage":"validate","pct":40}}
{"type":"error","diagnostic":{"rule":"BND001","severity":"error","message":"..."}}
{"type":"stream_end","ok":false,"counts":{"error":1,"warning":2,"info":0}}
```

`stream_end` is **sole terminator** (Phase 2 decision B1). Absence before socket close → bridge emits SDC006.

### Bridge WS

**Inbound** (renderer→bridge):
```
{"id":"req-42","type":"forgeds:cli:lint","data":{"paths":["..."]}}
{"id":"req-43","type":"forgeds:cli:bundle","data":{"spec_path":"..."}}
{"id":"req-44","type":"forgeds:cli:deploy","data":{"spec_path":"...","deploy_intent_token":"dit_6f3a...","target":"dev"}}
{"id":"req-45","type":"forgeds:fs:read","data":{"path":"forgeds.yaml"}}
```

**Outbound** req/res:
```
{"id":"req-42","type":"forgeds:cli:lint:result","data":{"version":"1","tool":"forgeds-lint","diagnostics":[...]}}
```

**Outbound stream events** (one WS message per sidecar NDJSON line):
```
{"id":"req-43","type":"forgeds:stream","data":{"frame":{"type":"chunk","diagnostic":{...}}}}
{"id":"req-43","type":"forgeds:stream","data":{"frame":{"type":"stream_end","ok":true,"counts":{...}}}}
```

**Broadcast** (no `id`):
```
{"id":null,"type":"forgeds:diagnostics:broadcast","data":{"version":"1","tool":"forgeds-bridge","diagnostics":[{"rule":"SDC003","severity":"warning","message":"sidecar restart 1/3 in 5min"}]}}
```

### Port-file
```
{"port":9877,"pid":12345,"started_at":"2026-04-24T14:22:01.123456Z"}
```

## 5. Lifecycle diagrams

### Spawn → first request → shutdown
```
Renderer   Bridge                 SidecarClient        Sidecar Process       PortFile
   |---WS:forgeds:cli:lint--->|                              -                 -
                              |--ensure_running()----->|                       -
                              |                        |--read_port_file-->|(none)
                              |                        |--Popen([py,-m,forgeds.sidecar])-->|
                              |                        |                         |--bind 9877--write-->|
                              |                        |<----poll port-file (≤3s)----|
                              |                        |--GET /health (500ms)--->|
                              |                        |<---200 {version:1}------|
                              |                        |<-(alive)
                              |--invoke(/forgeds/lint)------------------------->|
                              |<-------v1 envelope JSON-------------------------|
   |<--forgeds:cli:lint:result-|
   |
   | (user closes IDE)
   |                          |--shutdown()----->|--POST /shutdown------------->|
                              |                  |<------200 {ok:true}----------|
                                                                             process.shutdown() via daemon thread
                                                                             atexit: remove port-file -->|(gone)
```

### Crash recovery (budget)
```
t=0s   spawn#1 --crash--> respawn (1/3, 5min window)  -> broadcast SDC003 "1/3"
t=90s  spawn#2 --crash--> respawn (2/3)               -> broadcast SDC003 "2/3"
t=200s spawn#3 --crash--> respawn (3/3)               -> broadcast SDC003 "3/3"
t=250s spawn#4 --crash--> DENIED                       -> broadcast SDC004
                                                        -> SidecarClient marks dead; all invokes fail SDC001 until 5min rolls
```

### Two-window race
```
Window A spawns (port 9877 taken). PortFile written.
Window B boots -> ensure_running() -> read port-file -> GET /health -> 200 -> reuse.
No new spawn. Both windows share the sidecar. Shutdown is last-one-out (`POST /shutdown` only when no _sidecar_clients remain — deferred to 2D.x; 2D.1 ships first-in-wins, both POST on graceful close is acceptable since second POST hits closed socket harmlessly).
```

### Heartbeat miss
```
t=0s    HB tick -> /health 200 -> miss=0
t=30s   HB tick -> timeout     -> miss=1
t=60s   HB tick -> timeout     -> miss=2
t=90s   HB tick -> timeout     -> miss=3 -> broadcast SDC005; _process=None
next forgeds:* message -> ensure_running() sees no process -> _spawn_fresh (counts against restart budget)
```

## 6. Error & diagnostic flow

| Rule | Emitted at | Trigger | Payload | Consumer |
|---|---|---|---|---|
| `SDC001` | `handlers.py:_handle_forgeds_message` except `SidecarUnreachable` | `ensure_running()` fails after respawn attempt | v1 envelope tool=`forgeds-bridge`; `diagnostic.file = ".forgeds-sidecar.port"` | DiagnosticsRenderer shows "sidecar unreachable" banner |
| `SDC002` | `sidecar_client.py:_validate_health` | port-file shape bad or `/health` body missing `tool`/`version` | includes `actual_body` truncated 200 chars | renderer toast; stale port-file deleted |
| `SDC003` | `sidecar_client.RestartBudget.record_and_check → "warn"` | restart within budget | `attempt`, `window_sec`, `remaining` | renderer shows warning count; broadcast via `broadcast_sidecar_diagnostic` |
| `SDC004` | same, `→ "exceeded"` | 4th restart in 5min | same + `halted_until_sec` | renderer disables forgeds-cli buttons (2D.2) |
| `SDC005` | `sidecar_client._heartbeat_tick` when miss==3 | 3 consecutive /health failures | `miss_count`, `last_success_ts` | same broadcast path |
| `SDC006` | `sidecar_client.invoke_stream` when socket closes without `stream_end` | framing failure | `request_id`, `last_frame_type`, `bytes_received` | per-request `forgeds:stream` with error frame |
| `SDC010` | `_handle_forgeds_message` else-branch | unknown `forgeds:*` type | `unknown_type` | developer-mode only; logged |
| `SDC020` | `_handle_forgeds_message` deploy branch | token missing/replayed | `reason ∈ {"missing","replayed"}` | renderer forces re-click |

Mapping: sidecar in-band `{"type":"error","diagnostic":{...}}` → `sidecar_client.invoke_stream` unwraps frame, wraps as `{"type":"forgeds:stream","data":{"frame":<original>}}` WS message → renderer `DiagnosticsRenderer.tsx` receives frame, dispatches to severity-pane (stub in 2D.1).

## 7. Test strategy

| File | Test | Purpose |
|---|---|---|
| `tests/sidecar/test_sidecar_lifecycle.py` | `test_spawn_writes_port_file` | Popen sidecar, assert port-file appears with valid JSON within 3s |
| ″ | `test_health_endpoint_shape` | GET /health returns tool/version/status |
| ″ | `test_shutdown_endpoint_exits_cleanly` | POST /shutdown; process exits 0; port-file removed |
| ″ | `test_version_header_present` | `X-Forgeds-Sidecar-Version: 1` on all responses |
| `tests/sidecar/test_sidecar_port_file_rewrite.py` | `test_atomic_write_on_exdev` | mock os.replace to raise EXDEV; assert copyfile fallback path |
| ″ | `test_stale_port_file_overwritten` | pre-create bad port-file; spawn sidecar; assert overwritten |
| ″ | `test_shape_validation_rejects_missing_keys` | port-file missing `pid` → read returns None |
| `tests/sidecar/test_sidecar_restart_budget.py` | `test_restart_budget_warns_at_each_attempt` | mock _spawn_fresh to fake crash; assert SDC003 with attempt=1,2,3 |
| ″ | `test_restart_budget_exceeded_emits_sdc004` | 4th attempt within 5min → SDC004 broadcast, SidecarBudgetExceeded raised |
| ″ | `test_budget_window_rolls` | advance fake clock 301s; budget resets |
| `tests/sidecar/test_sidecar_streaming.py` | `test_bundle_streams_ndjson` | POST /forgeds/bundle; read chunks; assert ≥1 chunk + stream_end |
| ″ | `test_stream_end_terminates` | presence of stream_end is the sole close signal |
| ″ | `test_premature_close_raises_sdc006` | kill sidecar mid-stream; client raises frame-error with rule SDC006 |
| ″ | `test_inband_error_frame_contains_envelope` | induce tool error; assert `{type:error,diagnostic:{...v1...}}` |
| `tests/sidecar/test_sidecar_fs_read.py` | `test_fs_read_under_cap_returns_full` | 50KB file → full content |
| ″ | `test_fs_read_over_cap_returns_summary` | 200KB file → truncated summary shape |
| ″ | `test_fs_read_binary_refused` | PNG → `{ok:false,reason:"binary"}` |
| `tests/sidecar/test_deploy_intent_token_skeleton.py` | `test_deploy_intent_token_required` | `forgeds:cli:deploy` without token → SDC020 |
| ″ | `test_deploy_intent_token_replay_rejected` | same token twice → SDC020 second time |
| ″ | `test_deploy_intent_token_bound_to_request_id` | token tied to specific `id`; cross-id use refused |
| `bridge/tests/test_forgeds_router.py` | `test_unknown_forgeds_type_emits_sdc010` | `forgeds:cli:bogus` → SDC010 |
| ″ | `test_cli_lint_ws_roundtrip` | end-to-end lint via bridge WS |
| ″ | `test_cli_bundle_streaming_roundtrip` | bundle stream → multiple `forgeds:stream` events |
| ″ | `test_broadcast_reaches_all_authenticated_clients` | 2 mock WS; SDC003 broadcast → both receive |
| `bridge/tests/test_sidecar_client.py` | `test_health_probe_500ms_timeout` | slow sidecar → timeout → SDC001 |
| ″ | `test_lazy_spawn_on_first_request` | no spawn until first forgeds:* |
| ″ | `test_heartbeat_three_misses_marks_dead` | 3 consecutive timeouts → SDC005 |
| `bridge/tests/test_bridge_strips_auth_headers.py` | `test_bridge_strips_auth_headers` (placeholder) | asserts Authorization header not forwarded to sidecar HTTP (defensive; sidecar is local-only) |

## 8. Gotchas & mitigations (Windows-focused)

| Risk | Mitigation |
|---|---|
| `wfile` batching on Windows (research #1) | `StreamingWriter.write_frame` calls `self.wfile.flush()` unconditionally after every line; test `test_bundle_streams_ndjson` reads with short socket timeout (250ms) to catch regression |
| `os.replace` EXDEV across volumes (research #4) | mirror `spec_loader.py:247-325` — catch `OSError.errno == errno.EXDEV`, `shutil.copyfile` + `os.remove(tmp)` fallback |
| Encoding drift (Phase 2B used system locale) | all `json.dumps` → `.encode("utf-8")`; all reads via `open(p, "r", encoding="utf-8")`; NEVER rely on `sys.getdefaultencoding()` |
| `ThreadingHTTPServer.shutdown()` deadlock from handler thread (research #2) | `/shutdown` handler spawns daemon `Thread(target=server.shutdown)` AFTER writing 200 response |
| Port 9877 EADDRINUSE masking | explicit `errno.EADDRINUSE` (10048 Windows) check; do NOT set `allow_reuse_address` (research #3) |
| Subprocess zombie on bridge crash | sidecar registers `atexit` + `signal.signal(SIGTERM, graceful_shutdown)`; next bridge boot finds stale port-file and overwrites |
| `subprocess.Popen` CREATE_NEW_PROCESS_GROUP on Windows needed for clean SIGBREAK | use `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` when `sys.platform == "win32"` |
| Path separators in fs:read | always `Path(p).resolve()`; reject resolved paths outside project root |
| Port-file race (two windows start simultaneously) | accept as best-effort; second writer's `os.replace` wins atomically; both sidecars alive briefly is OK since heartbeat will drop one when port probe finds the winner |

## 9. Composability hooks (gap-close merge plan)

**Router placement** — `forgeds:*` elif goes AFTER the 13 flat elifs in `bridge/server.py:_handle_message` (post-line-151), BEFORE the unknown-type fallthrough. Rationale: gap-close's cancellation shortcut at 82-90 stays untouched; gap-close's touched elifs (`handle_ai_chat` signature change) are earlier in the chain so merge order doesn't matter; the new `forgeds:*` branch is self-contained and won't collide with any gap-close additions (gap-close is additive to `chat:*` / `mock:*` namespaces).

**Registry name** — `_sidecar_clients: dict[str, ClientContext]` deliberately avoids `_clients` (too generic; gap-close may add `_chat_clients`) and `_authenticated_clients` (implies auth-layer ownership, which belongs elsewhere). `_sidecar_clients` scopes clearly to the broadcast surface introduced by 2D.1.

**ai_chat signature** — if gap-close has already merged and `handle_ai_chat(..., send_fn: SendFn | None = None)` is present, `_handle_forgeds_message` accepts the same `send_fn` parameter; no friction. If 2D.1 merges first, gap-close's signature change is additive to their own function and doesn't touch ours.

**session_store collision** — our consumed-intent-token set is named `_deploy_intent_ledger` on `BridgeServer` (not `deploy_intent_session_store`). Leaves `bridge/session_store.py` (conversation history per gap-close) in a separate namespace. 2D.4 will decide if the ledger graduates to its own file; for 2D.1 it's an in-memory set on the server instance.

**Dependencies** — `bridge/requirements.txt` gets NO additions (sidecar is stdlib; bridge already has `websockets`). `pyproject.toml` gets `forgeds-sidecar = "forgeds.sidecar.__main__:main"` in `[project.scripts]`. The `websockets` import in `bridge/server.py` is pre-existing debt per research #12; flag in open-questions, do not fix in 2D.1.

## 10. Open questions / risks for Phase 5 (spec) + Phase 6 (plan)

1. **Multi-window shutdown coordination** — if two IDE windows share one sidecar, which triggers `POST /shutdown`? Best-effort-both is acceptable for 2D.1 but 2D.6 (operator docs) will need a clear statement. Propose: sidecar tracks a connection-count of bridges via a new `/register` endpoint? Or leave as OS-level cleanup via `atexit`?
2. **Deploy-intent-token lifetime** — 2D.1 ledger is an unbounded in-memory set. 2D.4 must decide expiry policy (TTL? bounded LRU? persistent across bridge restart?). Spec needs to answer before 2D.4 builds verify.
3. **`websockets` dependency classification** — `pyproject.toml` claims zero-dep but `bridge/server.py` imports `websockets`. Proposal: declare `bridge` as `[project.optional-dependencies] bridge = ["websockets>=11"]`. Needs user sign-off; deferred from 2D.1 to avoid scope creep but blocks CI install reproducibility.
4. **Streaming backpressure** — if sidecar emits 10,000 chunks faster than WS can send, bridge memory balloons. 2D.1 does not implement backpressure. 2D.3 (verify/watchdog) should revisit; spec should note it.
5. **Sidecar log surface** — currently `log_message` is no-op'd. Where do sidecar errors go? Propose: stderr + optional `--log-file` arg. Needs user decision on default location (stderr vs. `.forgeds-sidecar.log` next to port-file).
6. **100 KB fs:read cap — configurable?** Hard-coded for 2D.1. 2D.6 may want `forgeds.yaml`-configurable. Flag for spec.
7. **Test-only override env var consistency** — deploy spike uses `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY`. Should 2D.1's in-process sidecar spawn (for tests that want to bypass subprocess) use a parallel `FORGEDS_SIDECAR_INPROCESS_TESTONLY`? Recommend yes, for symmetry and to avoid flaky subprocess tests on slow Windows CI.
