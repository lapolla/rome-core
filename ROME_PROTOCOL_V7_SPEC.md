# ROME Protocol v7.1.0 Specification
**Status:** ACTUAL | **Authority:** Absolute | **Version:** 7.1.0

## 1. Overview: WebSocket-Native Signal Mesh
ROME v7.1.0 establishes a fully distributed, WebSocket-native orchestration mesh. Peer-to-peer communication is handled via structured JSON frames, moving away from legacy stdout regex-tagging.

## 2. WebSocket Signal Bus
Agents (Legions) interact with the ROME daemon via a dedicated WebSocket connection. This "Signal Bus" provides a clean separation of the data plane (agent output) and the control plane (orchestration commands).

### Transport
Agents connect to the daemon using the following environment variables:
- `ROME_WS_URL`: The WebSocket endpoint (e.g., `ws://127.0.0.1:8741`).
- `ROME_WS_TOKEN`: The sovereign authentication token.

### Handshake
On connection, a subprocess agent binds itself to its parent task:
```json
{
  "type": "signal_hello",
  "task_id": "ts-xxxxxxxx"
}
```

## 3. Command Protocol (The V7 Pulse)
Once connected, agents emit commands as structured JSON frames. This is the same protocol used by the CLI and persistent workers.

| Command | Action | Payload |
|---------|--------|---------|
| `dispatch` | Spawn a sub-task | `{ "capability": "...", "prompt": "..." }` |
| `await` | Block for task completion | `{ "task_id": "..." }` |
| `native_shell` | Execute daemon-level bash | `{ "command": "..." }` |
| `read_file` | Read a local file | `{ "file_path": "..." }` |
| `write_file` | Write/Create a file | `{ "file_path": "...", "content": "..." }` |
| `status` | Query mesh/task state | `{}` |

## 4. Response & Event Handling
The daemon responds with a standard response frame:
```json
{
  "type": "response",
  "request_id": "sig-1",
  "ok": true,
  "payload": { "task_id": "ts-def67890" }
}
```
Agents also receive asynchronous events (e.g., `progress`, `complete`, `error`) via the same WS connection for any tasks they have dispatched.

## 5. Legacy Support (DAS Tags)
While the WebSocket Signal Bus is the primary protocol, the `[ROME_DISPATCH: ...]` and `[ROME_SHELL: ...]` tags are maintained for backwards compatibility with non-WS-aware agents. These are intercepted via stdout by the `legion_worker` wrapper.

---
**"The agent is the orchestrator. The mesh is the medium. ROME is the mind."**
