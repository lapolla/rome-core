# ROME Signal Bus (RSB) — DAS Replacement Spec

**Status:** PLANNED | **Replaces:** V6 DAS stdout tag protocol | **Version:** 7.0.0

## Problem

The V6 DAS protocol embeds structured signals as regex-parseable tags in the agent's stdout stream:

```
[ROME_DISPATCH: SAFE_SHELL "ls -la"]
[ROME_AWAIT: ts-abc12345]
[ROME_READ: /path/to/file]
[ROME_SHELL: "command here"]
```

The worker does `readline` on stdout, regex-matches every line for `[ROME_` prefixes, parses the tag, executes the action, and injects JSON responses into the agent's stdin.

This is bad because:

1. **False positives** — any LLM output containing `[ROME_` triggers signal parsing. An agent discussing the protocol, quoting logs, or generating docs will fire spurious signals.
2. **Fragile parsing** — each signal type needs its own regex with bespoke capture groups. Prompts with quotes, newlines, or special chars break extraction.
3. **Stdout pollution** — control plane and data plane share one stream. The worker must process every byte of output to find signals, and the agent's actual report content is interleaved with signal tags.
4. **Stdin coupling** — the response goes back on stdin, which creates ordering hazards. If the agent emits two signals before reading stdin, the responses pile up and desync.
5. **Hard to extend** — adding a new signal means writing a new regex, updating `parseRomeSignals`, updating `handleRomeSignal`, updating the spec doc. Four places minimum.
6. **No typing** — payloads are positional strings extracted from regex groups, not structured objects. The dispatch signal crams capability and prompt into `CAP "prompt"` format.

## Design: WebSocket Signal Bus

Agents connect to the **same WS server** that already exists. A subprocess agent opens a WS connection to the daemon, authenticates, identifies itself with its `task_id`, and then sends/receives structured JSON signal frames — exactly the same protocol shape the daemon already speaks.

No new server. No new port. No HTTP. Pure WS, same as everything else in ROME.

### Transport

Agent connects on startup:

```
ws://127.0.0.1:{port}?token={TOKEN}
```

Immediately sends a hello that binds this connection to its task:

```json
{
  "type": "signal_hello",
  "task_id": "ts-abc12345"
}
```

Daemon responds:

```json
{
  "type": "signal_ack",
  "ok": true,
  "task_id": "ts-abc12345"
}
```

Then the agent sends signal requests as standard ROME command frames:

```json
{
  "type": "command",
  "command": "dispatch",
  "request_id": "sig-1",
  "payload": { "capability": "SAFE_SHELL", "prompt": "ls -la" }
}
```

Daemon responds with the same response frame shape it already uses:

```json
{
  "type": "response",
  "request_id": "sig-1",
  "ok": true,
  "payload": { "task_id": "ts-def67890", "routed_to": "worker" }
}
```

**This is literally the existing WS command protocol.** The only new thing is `signal_hello` to bind a connection to a parent task. Everything else — `dispatch`, `await`, `read_file`, `write_file`, `native_shell`, `status` — already exists as daemon commands. The agent just uses them directly.

### Why This Works

The 20 WS commands in PeerServer already cover every signal type DAS tried to reinvent:

| Dead DAS Tag | Existing WS Command | Already Implemented |
|---|---|---|
| `[ROME_DISPATCH: CAP "prompt"]` | `dispatch` | Yes |
| `[ROME_AWAIT: task_id]` | `await` | Yes |
| `[ROME_READ: path]` | `read_file` | Yes |
| `[ROME_SHELL: "cmd"]` | `native_shell` | Yes |
| `[ROME_STATUS: SUCCESS]` | `submit_result` | Yes |
| `[ROME_META: key=val]` | `event` | Yes |
| `[ROME_START]...[ROME_END]` | `write_file` | Yes |

DAS was a shitty text reimplementation of a protocol that already existed one layer up. The fix isn't a new transport — it's letting subprocess agents talk the same WS protocol that persistent workers and the CLI client already speak.

### What `signal_hello` Does

When the daemon receives `signal_hello`:

1. Validates `task_id` exists in the TaskRegistry
2. Binds this WS connection as the **signal channel** for that task (stored in a `Map<string, WebSocket>`)
3. Subscribes the connection to EventBus (so the agent can receive events for tasks it dispatched)
4. Returns `signal_ack`

On disconnect: cleanup the binding. If the task is still running, it continues — the signal channel is optional, not load-bearing.

### What Dies

Deleted entirely:

- `parseRomeSignals()` — 60 lines of regex
- `handleRomeSignal()` — signal dispatch function
- `RomeSignals` interface
- `PendingSignal` interface
- `SignalHandler` type
- The `signalHandler` callback parameter threaded through `executeTask()` and `PeerServer.runLegion()`
- The `readline` interception loop in `executeTask()` (lines 498-514) — replaced with plain `child.stdout?.on('data', buf => ui.handleBytes(buf))`
- The `child.stdin?.write(JSON.stringify(res))` response injection
- All `[ROME_*]` tag formats
- `[ROME_SIGNAL:]` regex in `aaak/compress.ts`

### What Changes

**`peer_server.ts`** — add `signal_hello` handling in the `ws.on('message')` handler:

```typescript
if (msg.type === 'signal_hello') {
  const taskId = msg.task_id;
  if (!this.registry.get(taskId)) {
    ws.send(JSON.stringify({ type: 'signal_ack', ok: false, error: 'Unknown task' }));
    return;
  }
  this.signalChannels.set(taskId, ws);
  ws.send(JSON.stringify({ type: 'signal_ack', ok: true, task_id: taskId }));
  return;
}
```

After that, commands from signal connections are handled by the **exact same `handleCommand()`** that handles everything else. Zero new command logic.

**`peer_server.ts`** — cleanup: add to `ws.on('close')`:

```typescript
// Clean up signal channel binding
for (const [tid, sock] of this.signalChannels.entries()) {
  if (sock === ws) this.signalChannels.delete(tid);
}
```

**`peer_server.ts`** — new field:

```typescript
private signalChannels = new Map<string, WebSocket>();
```

**`executeTask()`** — simplified dramatically:

```typescript
// Before: readline + regex + stdin injection (20 lines)
// After: just stream stdout for progress, nothing else
child.stdout?.on('data', (buf: Buffer) => {
  stdoutChunks.push(buf);
  ui.handleBytes(buf);
});
child.stderr?.on('data', (buf: Buffer) => stderrChunks.push(buf));
```

No more `readline` interface. No more `for await (const line of rl)`. No more signal parsing. The agent handles its own signaling over WS.

**`executeTask()` signature** — remove `signalHandler` parameter:

```typescript
// Before:
export async function executeTask(
  taskId, capabilityName, cmdArgs, wsSender?, modelChain?, signalHandler?
)

// After:
export async function executeTask(
  taskId, capabilityName, cmdArgs, wsSender?, modelChain?
)
```

**`PeerServer.runLegion()`** — remove the `signalHandler` callback (currently 20 lines defining dispatch/await/shell handlers). The daemon's existing `handleCommand()` does all of this already when the agent connects via WS.

**`LegionaryUI.handleBytes()`** — unchanged. Progress heuristics still observe stdout.

### Environment Contract

The worker sets these env vars on the spawned process:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ROME_WS_URL` | `ws://127.0.0.1:{port}` | Daemon WS endpoint |
| `ROME_WS_TOKEN` | `{token}` | Auth token |
| `ROME_TASK_ID` | `ts-xxxxxxxx` | Task ID (unchanged) |
| `ROME_TASK_DIR` | `/path/to/legions/{task_id}` | Working directory (unchanged) |
| `ROME_ROOT` | `/path/to/rome-core` | Project root (unchanged) |

The agent connects to `$ROME_WS_URL?token=$ROME_WS_TOKEN`, sends `signal_hello` with `$ROME_TASK_ID`, then uses the standard command protocol.

### Agent-Side Helper

A tiny Node one-liner agents can use (or equivalent in any language with a WS library):

```bash
# In legion_patches.json prompt injection:
# "To interact with ROME, use your shell tool to run the rome-signal helper."

# rome-signal helper (ships as src/signal_client.sh or similar):
rome_signal() {
  node -e "
    const ws = new (require('ws'))('$ROME_WS_URL?token=$ROME_WS_TOKEN');
    ws.on('open', () => {
      ws.send(JSON.stringify({type:'signal_hello',task_id:'$ROME_TASK_ID'}));
      ws.send(JSON.stringify({type:'command',command:'$1',request_id:'s'+Date.now(),payload:$2}));
    });
    ws.on('message', d => {
      const m = JSON.parse(d);
      if (m.type === 'response') { console.log(JSON.stringify(m)); ws.close(); }
    });
  "
}
```

But realistically, agents that need signal access (GEMINI, CLAUDE, CODEX) already have shell tools. They just run a short script. LLM CLI tools that support MCP can skip this entirely (see Future section).

### Authentication

Same as existing WS auth — token via `?token=` query param or `Authorization: Bearer` header. Subprocess agents get the token via `ROME_WS_TOKEN` env var. No new auth mechanism.

### Persistent Workers

Unchanged. Persistent workers already connect via WS with `agent_hello` and use the command protocol for everything. The `signal_hello` handshake is the subprocess equivalent of `agent_hello` — it just binds to an existing task instead of registering capabilities.

| Connection Type | Hello | Purpose |
|---|---|---|
| CLI client | (none) | Send commands, receive events |
| Persistent worker | `agent_hello` | Register capabilities, receive dispatches |
| Subprocess agent | `signal_hello` | Bind to parent task, send commands |
| Dashboard | (none, same-origin bypass) | Read-only events |

### AAAK Compress Update

Delete the `[ROME_SIGNAL:]` regex from `extractChanges()` in `aaak/compress.ts`. Signals no longer appear in report text.

### Migration Path

1. **Add `signal_hello` handling** to PeerServer WS message handler + `signalChannels` map + cleanup on close. (~15 lines)
2. **Set `ROME_WS_URL` + `ROME_WS_TOKEN` env vars** in `executeTask()` spawned process environment. (~3 lines)
3. **Strip `executeTask()` signal loop** — remove readline, stdin injection, signalHandler param. Replace with plain stdout streaming. (~-30 lines)
4. **Strip `runLegion()` signalHandler** callback in PeerServer. (~-20 lines)
5. **Delete** `parseRomeSignals`, `handleRomeSignal`, `PendingSignal`, `RomeSignals`, `SignalHandler`. (~-90 lines)
6. **Delete** `[ROME_SIGNAL:]` regex in `aaak/compress.ts`. (~-3 lines)
7. **Update `legion_patches.json`** — tell agents about WS signal protocol instead of `[ROME_*]` tags.
8. **Write `src/signal_client.sh`** — optional helper for agents.

Steps 1-2 are additive (no breakage). Steps 3-6 land together. Net: ~15 lines added, ~140 lines deleted.

### Future: MCP Native Signals

The end-state: PeerServer exposes an **MCP endpoint** that maps ROME commands to MCP tools. Claude CLI, Gemini CLI, and any MCP-aware agent get `rome_dispatch`, `rome_await`, `rome_read`, `rome_shell` as first-class tool calls with typed schemas — no shell helper, no prompt engineering. The WS signal bus is the universal fallback for non-MCP agents.
