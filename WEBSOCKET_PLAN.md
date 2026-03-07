# WebSocket Transport Implementation Plan for ROME

## Goal

Implement Option B, a unified persistent daemon for ROME:

- `dictator` stays the single orchestration process.
- Claude Code connects to the MCP server over SSE instead of stdio.
- External clients connect over WebSocket for live dispatch control and event streaming.
- The daemon also serves a lightweight dashboard and later a Python client SDK.

This plan is based on the current ROME codebase in `/home/paul-kane/projects/rome-core`:

- `dictator/core.py` owns config, shared paths, `run_cmd`, `run_cmd_stream`, and the `FastMCP` instance.
- `dictator/dictator.py` is the current stdio-only entrypoint.
- `dictator/tools_legion.py` contains the real dispatch lifecycle in `_execute_legion_impl`, plus campaign orchestration.
- `legions/legion_wrapper.py` already emits structured progress and parses usage and `[ROME_META]` / `[ROME_STATUS]` tags.
- `arsenal/core_arsenal.json` is the runtime registry for agent capabilities.
- `requirements.txt` currently only pins `fastmcp>=3.1.0`.

`FastMCP` in the installed environment already exposes `sse_app()` and `run(..., transport="sse")`, so the transport migration should build around its ASGI support instead of replacing MCP internals.

## Target Architecture

Run one ASGI process with three surfaces:

1. MCP-over-SSE for Claude Code.
2. Native WebSocket API for dashboards, CLI clients, and other AI agents.
3. Static dashboard assets served by the same process.

The daemon should own:

- A process-local async event bus.
- An in-memory registry of active legion tasks.
- A WS connection manager with auth and fan-out.
- The mounted FastMCP SSE app.

Recommended route layout:

- `/mcp/*` for FastMCP SSE transport.
- `/ws` for WebSocket clients.
- `/api/status` for simple HTTP readiness and daemon state.
- `/dashboard` for the browser UI.
- `/static/*` for dashboard assets if split into multiple files.

## Cross-Cutting Design Decisions

### Event model

Define a single event envelope used internally and over WebSocket:

```json
{
  "type": "progress",
  "task_id": "TASK_123",
  "ts": 1741305600.123,
  "source": "execute_legion",
  "sequence": 42,
  "payload": {
    "percent": 55,
    "message": "Running tests..."
  }
}
```

Recommended event types for phase 1:

- `dispatch_start`
- `progress`
- `complete`
- `error`
- `cost_update`
- `campaign_update`
- `heartbeat`

### Command model

WebSocket messages should be explicit command envelopes:

```json
{
  "type": "command",
  "command": "dispatch",
  "request_id": "req_001",
  "payload": {
    "task_id": "TASK_123",
    "capability": "CODEX",
    "args": ["..."],
    "input_files": []
  }
}
```

Initial commands:

- `dispatch`
- `cancel`
- `status`
- `subscribe`
- `ping`

### Task state

Do not force the dashboard or SDK to reconstruct state from raw logs. Add a daemon-owned task registry keyed by `task_id`:

- status
- capability
- started_at / updated_at / finished_at
- last progress percent and message
- usage and cost totals
- report path
- legion directory
- cancel handle if active

This state store is required for `status` commands and reconnect behavior.

### Auth

Keep auth simple for v1:

- Add `ws_token` and `daemon_bind` / `daemon_port` to `dictator/config.json`.
- Require the token on WS connect via header or query param.
- Reuse the same token for the dashboard JS.
- Keep SSE auth separate; Claude Code usually connects on localhost, so start with localhost binding and optional reverse-proxy hardening later.

## Phase 1: Event Bus

**Complexity:** `M`

### Objective

Create a process-local async event bus in `dictator/core.py` and make legion execution emit structured lifecycle events.

### Files to modify

- `dictator/core.py`
- `dictator/tools_legion.py`
- `legions/legion_wrapper.py`
- `tests/test_dictator.py`

### Files to create

- `dictator/events.py`

### Key code patterns

1. Add a typed event envelope and lightweight pub/sub bus.

Example shape:

```python
@dataclass(slots=True)
class RomeEvent:
    type: str
    task_id: str | None
    ts: float
    sequence: int
    source: str
    payload: dict[str, Any]
```

```python
class EventBus:
    def __init__(self, max_queue_size: int = 1000) -> None:
        self._subscribers: dict[str, asyncio.Queue[RomeEvent]] = {}
        self._sequence = 0
        self._lock = asyncio.Lock()

    async def publish(self, event: RomeEvent) -> None: ...
    async def subscribe(self) -> tuple[str, asyncio.Queue[RomeEvent]]: ...
    async def unsubscribe(self, subscriber_id: str) -> None: ...
```

2. Instantiate the bus in `dictator/core.py` next to `mcp`.

3. Centralize emission helpers so tools do not hand-roll payloads:

- `emit_dispatch_start(...)`
- `emit_progress(...)`
- `emit_complete(...)`
- `emit_error(...)`
- `emit_cost_update(...)`

4. Wire `_execute_legion_impl` to publish events at lifecycle boundaries:

- before capability lookup succeeds: `dispatch_start`
- while `run_cmd_stream(..., on_stderr=...)` receives progress: `progress`
- after `parse_usage(...)`: `cost_update`
- on success: `complete`
- on timeout / exception / bad capability: `error`

5. Reuse existing `legion_wrapper.py` parsing instead of inventing a second parser. When the wrapper extracts usage and `[ROME_META]`, include those fields in the final event payload.

6. Add a minimal in-memory task registry in either `dictator/events.py` or `dictator/core.py` so the daemon can answer `status` without scraping filesystem logs.

Suggested registry write points:

- create record at `dispatch_start`
- update percent/message on `progress`
- update usage on `cost_update`
- mark terminal state on `complete` / `error`

### Dependencies

- No new package is strictly required.
- Optional: `pydantic` for event schemas, but this is not necessary in phase 1.

### Testing approach

- Add unit tests for subscribe/publish/unsubscribe semantics.
- Add tests that `_execute_legion_impl(..., on_progress=...)` emits normalized `progress` events.
- Add tests that usage parsing produces `cost_update`.
- Add tests that failed capability lookup and timeout produce `error`.
- Keep tests direct and local, similar to existing `tests/test_dictator.py`.

### Practical implementation notes

- Use bounded `asyncio.Queue`s per subscriber. On overflow, prefer dropping the oldest event or disconnecting that subscriber later in phase 2; do not let a slow client stall the server.
- Preserve existing `ctx.info(...)` reporting for MCP callers; event bus emission should be additive, not a replacement.
- Do not emit raw stderr chunks as-is. Normalize them into `{percent, message}` once in the callback path.

## Phase 2: WS Server

**Complexity:** `L`

### Objective

Run `dictator` as a single ASGI daemon that mounts FastMCP SSE and exposes a WebSocket endpoint for external clients.

### Files to modify

- `dictator/core.py`
- `dictator/dictator.py`
- `dictator/config.json`
- `requirements.txt`
- `tests/test_dictator.py`

### Files to create

- `dictator/daemon.py`
- `dictator/ws_server.py`
- `tests/test_ws_server.py`

### Key code patterns

1. Build a parent ASGI app instead of calling `mcp.run(transport="stdio")`.

Recommended structure:

```python
def build_app() -> Starlette:
    mcp_app = mcp.sse_app("/mcp")
    routes = [
        Mount("/mcp", app=mcp_app),
        WebSocketRoute("/ws", endpoint=rome_ws_endpoint),
        Route("/api/status", endpoint=status_endpoint),
        Mount("/dashboard", app=dashboard_app),
    ]
    return Starlette(routes=routes)
```

2. Use `dictator/daemon.py` as the new startup surface:

- load config
- create shared app state
- run `uvicorn`

3. Implement a WS connection manager:

- authenticate on connect
- subscribe the client to the event bus
- serialize `RomeEvent` objects to JSON
- consume incoming commands and dispatch them to internal handlers

4. Add a command handler layer instead of mixing route logic with legion logic:

- `handle_dispatch`
- `handle_cancel`
- `handle_status`

5. Dispatch should run in background tasks, not inline in the WebSocket receive loop:

```python
task = asyncio.create_task(
    _execute_legion_impl(..., on_progress=emit_progress_callback)
)
active_tasks[task_id] = task
```

6. For cancel support, store the running `asyncio.Task` by `task_id` and call `task.cancel()`. In `_execute_legion_impl`, handle cancellation explicitly and emit a terminal `error` or `complete` with `status="cancelled"`.

7. Add a simple auth dependency:

- header: `Authorization: Bearer <token>`
- fallback query param: `?token=...`

8. Define message protocol explicitly.

Client-to-server:

```json
{"type":"command","command":"status","request_id":"1","payload":{"task_id":"TASK_123"}}
```

Server-to-client ack / response:

```json
{"type":"response","request_id":"1","ok":true,"payload":{"task_id":"TASK_123","status":"running"}}
```

Server-to-client event:

```json
{"type":"event","event":{"type":"progress","task_id":"TASK_123","payload":{"percent":70,"message":"Writing..."}}}
```

### Dependencies

- Add `uvicorn` for a production-ready ASGI entrypoint.
- `starlette` is already a transitive dependency of FastMCP, but pinning it explicitly is reasonable if the repo wants deterministic runtime behavior.
- `fastapi` is optional. Starlette alone is enough and is the lower-friction choice because `FastMCP.sse_app()` already returns a Starlette app.

Recommended `requirements.txt` additions:

- `uvicorn>=0.30`
- optionally `starlette>=0.37`

### Testing approach

- Use Starlette’s `TestClient` / websocket test session for auth and protocol coverage.
- Verify rejected unauthenticated connections.
- Verify `dispatch` returns an ack and subsequent event stream.
- Verify `status` returns from the task registry.
- Verify cancel produces terminal task state.
- Add a basic integration test mounting the real `mcp.sse_app("/mcp")` and the WS route together to catch route conflicts.

### Practical implementation notes

- Keep WS payloads JSON-only. Do not send mixed text frames.
- Send a heartbeat every 10-15 seconds so browsers and CLI clients can detect dead sockets cleanly.
- Mount the MCP app under `/mcp` from day one so future HTTP routes do not collide with transport paths.
- Keep daemon state process-local initially. Multi-process fan-out can wait; a single-process `uvicorn --workers 1` deployment is the right first target because dispatch state lives in memory.

## Phase 3: MCP Transport Switch

**Complexity:** `M`

### Objective

Move Claude Code from launching `dictator` over stdio to connecting to the persistent daemon over SSE, while preserving all existing MCP tools.

### Files to modify

- `dictator/dictator.py`
- `dictator/SOURCE_README.md`
- project `.mcp.json` or `~/.claude/mcp-servers.json` templates used by ROME operators
- deployment helper docs or scripts if present

### Files to create

- `ops/rome-dictator.service` or `ops/systemd/rome-dictator.service`
- optionally `scripts/run_dictator_daemon.sh`

### Key code patterns

1. Stop using `dictator/dictator.py` as a stdio-only main. Either:

- make it call the daemon builder, or
- preserve it as a compatibility wrapper and add a new daemon-first entrypoint.

2. Update Claude Code MCP configuration to point to the SSE endpoint instead of spawning the process directly.

3. Standardize daemon startup:

- `systemd` service for persistent local boot-time startup, or
- `tmux`/`screen` for manual development environments

4. Add health checks:

- `GET /api/status` returns daemon version, uptime, active task count
- optional `GET /dashboard` static page smoke test

### Dependencies

- No new Python dependency beyond phase 2.
- Optional OS dependency: `systemd` if using the service path.

### Testing approach

- Run the daemon locally and connect Claude Code over SSE.
- Verify tool discovery still returns the current 47 tools.
- Smoke-test representative tools from each module group:
  - file IO
  - git
  - legion dispatch
  - desktop/media if available in the host environment
- Confirm `ctx.info(...)` progress still reaches Claude Code over SSE.
- Confirm a long-running legion task still produces progress and completion without stdio deadlocks.

### Practical implementation notes

- Keep the existing stdio path behind a flag until SSE is proven. For example, allow `python3 dictator/dictator.py --transport stdio` during transition.
- Update docs carefully: current `SOURCE_README.md` still describes the old Node server and stdio launch model, so it needs a full transport/deployment rewrite.
- Prefer localhost binding by default. If remote access is needed later, place a reverse proxy or SSH tunnel in front of the daemon rather than exposing it directly at first.

## Phase 4: Dashboard

**Complexity:** `M`

### Objective

Serve a lightweight browser dashboard from the daemon and render live legion activity from WS events.

### Files to modify

- `dictator/daemon.py`
- `dictator/ws_server.py`

### Files to create

- `dictator/dashboard/index.html`
- `dictator/dashboard/app.js`
- `dictator/dashboard/styles.css`
- `tests/test_dashboard_assets.py`

### Key code patterns

1. Serve static assets directly from the daemon:

```python
routes.append(Mount("/dashboard", app=StaticFiles(directory=dashboard_dir, html=True)))
```

2. The browser app should:

- open `ws://.../ws?token=...`
- request current status snapshot on connect
- merge snapshot state with streaming events
- render one card per active or recent legion task

3. UI model per task card:

- task id
- capability
- status
- percent bar
- latest message
- elapsed time
- usage / token totals
- cost if known
- link to report path or legion dir

4. Keep the frontend dependency-free at first:

- plain HTML/CSS/JS
- no build step
- no React/Vite unless the dashboard scope expands materially

### Dependencies

- No new package required if using Starlette `StaticFiles`.

### Testing approach

- HTTP test for `/dashboard` returning `200`.
- Static asset smoke tests.
- Manual browser test with a real legion dispatch.
- Verify reconnect behavior by refreshing during an active task.
- Verify a client that connects mid-task gets snapshot state plus live events.

### Practical implementation notes

- The dashboard needs snapshot + stream. WS events alone are not enough for reload recovery.
- Keep visuals intentionally operational: dense grid, obvious status color states, readable progress, low ornamentation.
- Add a small event log panel so operators can see errors and cancellations without tailing files.

## Phase 5: Client SDK

**Complexity:** `M`

### Objective

Expose the WS API as a reusable async Python client for scripting and automation.

### Files to modify

- `requirements.txt`
- `dictator/__init__.py`

### Files to create

- `dictator/client.py`
- `tests/test_client_sdk.py`
- optionally `examples/ws_client_demo.py`

### Key code patterns

1. Provide a small async client:

```python
class RomeClient:
    async def __aenter__(self) -> "RomeClient": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def dispatch(self, task_id: str, capability: str, args: list[str], **kwargs) -> dict: ...
    async def cancel(self, task_id: str) -> dict: ...
    async def status(self, task_id: str | None = None) -> dict: ...
    async def stream_events(self) -> AsyncIterator[dict]: ...
```

2. Use request IDs internally so command responses can be matched while the event stream continues.

3. Expose both low-level and high-level operations:

- raw `send_command(...)`
- typed helpers for `dispatch`, `cancel`, `status`

4. Make reconnect policy explicit. For v1, fail fast and let callers reconnect intentionally; silent auto-reconnect will complicate event ordering.

### Dependencies

- Add `websockets>=12` or use `httpx` + `wsproto` stack if the repo already standardizes on that later.
- `websockets` is the simplest fit for an async SDK.

### Testing approach

- Spin up the Starlette app in tests and connect with the SDK.
- Verify `dispatch`, `status`, and `cancel`.
- Verify `stream_events()` yields normalized event envelopes.
- Verify auth failure path.

### Practical implementation notes

- Keep the SDK transport-specific. Do not mix MCP abstractions into it.
- The client should target the WS API only; Claude Code will keep using MCP-over-SSE.
- Document that the SDK is for orchestration control and live monitoring, not direct MCP tool invocation.

## Suggested Implementation Order

1. Build `dictator/events.py` and event emission in legion execution.
2. Add the in-memory task registry.
3. Build the Starlette daemon wrapper and mount FastMCP SSE under `/mcp`.
4. Add authenticated `/ws` with `status` first.
5. Add `dispatch`.
6. Add `cancel`.
7. Switch Claude Code MCP config to SSE.
8. Add the dashboard.
9. Add the Python SDK.

This order keeps the riskiest transport change behind a working internal event model, and it lets the dashboard and SDK reuse the same protocol rather than inventing separate code paths.

## Dependency Summary

Current:

- `fastmcp>=3.1.0`

Add in phase 2:

- `uvicorn>=0.30`
- optionally `starlette>=0.37`

Add in phase 5:

- `websockets>=12`

Not required initially:

- Redis
- Celery
- a frontend framework
- database persistence

## Risk Areas and Mitigations

### 1. Long-running task cancellation

Risk:
`asyncio.Task.cancel()` will not automatically terminate child subprocess trees created inside legion execution.

Mitigation:

- Track the subprocess handle where possible.
- Add explicit process-group management in `run_cmd_stream` or a legion-specific runner.
- Treat true process cancellation as a follow-up inside phase 2, not an afterthought.

### 2. Slow WS consumers

Risk:
One slow browser can create unbounded backpressure if event fan-out is naïve.

Mitigation:

- per-client bounded queues
- heartbeat timeouts
- disconnect lagging clients instead of stalling dispatch

### 3. State loss on daemon restart

Risk:
In-memory task state disappears on restart.

Mitigation:

- accept this for v1
- rebuild recent history from legion directories or `logs/rome.jsonl` later if required

### 4. Transport migration breakage

Risk:
Claude Code tool access could regress during the stdio-to-SSE switch.

Mitigation:

- keep stdio fallback briefly
- add a regression checklist covering all tool modules
- verify tool count and representative calls before removing stdio

## Definition of Done

The WebSocket transport work is done when:

- `dictator` runs as one persistent ASGI daemon.
- Claude Code connects to ROME over MCP SSE at `/mcp`.
- External clients can connect to `/ws`, authenticate, dispatch work, request status, and receive live events.
- The dashboard shows active legion tasks with live progress and cost updates.
- A Python `RomeClient` can drive the WS API asynchronously.
- Existing MCP tools still function over the new daemon transport.

