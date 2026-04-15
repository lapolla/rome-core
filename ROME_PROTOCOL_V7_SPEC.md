# ROME Protocol v7.0.2 Specification
**Status:** PROPOSED | **Authority:** Absolute | **Version:** 7.0.2

## 1. Overview: Agent-to-Agent Direct Signal Mesh (A2A-DSM)
ROME v7.0.2 evolves the orchestration model from a centralized "Dictator" pattern to a distributed, self-orchestrating mesh. Agents (Legions) are no longer passive executors of tasks; they are active participants in the mesh, capable of spawning sub-tasks, awaiting results, and interacting with the host system in real-time.

## 2. Direct Agent Signals (DAS)
The core of v7 is the **DAS Protocol**. Agents emit structured signals in their stdout stream. The ROME worker intercepts these signals, executes the requested action, and feeds the result back to the agent via its stdin.

### Signal Tags

| Tag | Action | Payload | Response (JSON) |
|-----|--------|---------|----------------|
| `[ROME_DISPATCH: <CAP> "<PROMPT>"]` | Dispatch a sub-task | Capability + Prompt | `{"ok": true, "task_id": "..."}` |
| `[ROME_AWAIT: <TASK_ID>]` | Block until task completes | Task ID | `{"ok": true, "status": "SUCCESS", "report": "..."}` |
| `[ROME_READ: <PATH>]` | Read a local file | File Path | `{"ok": true, "content": "..."}` |
| `[ROME_SHELL: "<CMD>"]` | Execute a bash command | Bash Command | `{"ok": true, "report": "...", "exit_code": 0}` |

## 3. Real-Time Interaction Loop (The "V7 Pulse")
The worker-to-agent communication follows a synchronous request-response pattern over stdio:
1. **Emit:** Agent writes `[ROME_DISPATCH: SAFE_SHELL "ls -la"]` to stdout.
2. **Intercept:** Worker detects `[ROME_` prefix, parses the tag.
3. **Execute:** Worker calls the PeerServer's internal dispatcher.
4. **Respond:** Worker writes `{"ok": true, "task_id": "ts-abc12345"}` + `\n` to Agent's stdin.
5. **Continue:** Agent reads stdin and proceeds (e.g., to await that task).

## 4. Mesh Sovereignty & Recursive Dispatch
V7 removes the distinction between "parent" and "child" orchestrators. Every PeerServer can handle recursive dispatches. Agents can build dynamic DAGs at runtime based on the feedback they receive from the system.

## 5. Security & Safety (DSA v2)
Direct Shell Access (DSA) in v7 is gated by the `SAFE_SHELL` capability. Agents must explicitly use the `[ROME_SHELL: ...]` or `[ROME_DISPATCH: SAFE_SHELL ...]` signals, which are audited by the PeerServer.

---
**"The agent is the orchestrator. The mesh is the medium. ROME is the mind."**
