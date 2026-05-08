# ROME: Remote Orchestrated Model Execution

A WebSocket-native orchestration mesh. The Dictator decomposes goals and routes subtasks to worker Legions via the WS daemon (`ROME_WS_URL`, default `ws://127.0.0.1:8741`).

## Architecture

| Component | Path | Role |
|---|---|---|
| **Daemon** | `src/peer_server.ts` | WS server. Routes dispatches, tracks tasks, broadcasts events on the bus. |
| **Native Agent** | `src/native_agent.ts` | LLM worker process. Connects back to the daemon via WS on spawn. Intercepts DAS signals from model output. |
| **Shell Executor** | `src/shell_executor.ts` | Bash executor for `NATIVE_SHELL`. Exit code is authoritative — no LLM interpretation. |
| **Registry** | `src/registry.ts` | `EventBus`, `TaskRegistry`, `WorkerRegistry`. Persists task state to disk. |
| **AAAK** | `src/aaak/` | Semantic cache, memory, and response compression subsystem. |
| **Arsenal Probe** | `src/arsenal_probe.ts` | Checks worker availability before dispatch. |
| **CLI Dispatcher** | `src/client.ts` | Headless task dispatcher for external callers. |
| **Launcher** | `ROME-start.sh` | Compiles TS and starts the mesh. |
| **Dashboard** | `dashboard/index.html` | Live task monitor, subscribes to the WS bus. |
| **Worker Config** | `dictator/workers.json` | Capability definitions — invocation type, probe command, model, CLI command. |

See **`CLAUDE.md`** for the full WS command schema and protocol rules.

## ⚡ Every Worker is a Mesh Node

**This is the property that bites you if you forget it.**

Every worker spawned by `native_agent_cli` — CLAUDE, OPUS, HAIKU, GEMINI, MISTRAL — connects back to `ws://127.0.0.1:8741` on spawn. Workers are **not** isolated subprocesses returning text. They are full mesh participants: they can sub-dispatch, read/write blackboard state, emit progress events, and receive cancellation signals — all over the same WS connection.

**Implications:**
- A CLAUDE/OPUS worker that dispatches further is a recursive Dictator inside the mesh. It inherits all parent constraints. If GEMINI is fenced, a sub-dispatch from inside that worker hits the same fence — and fails silently.
- Progress events stream to the bus in real time. No polling needed.
- Sub-tasks dispatched from inside a worker appear in the registry alongside parent tasks. The mesh is always deeper than one level.

## Workers

Cost gradient — cheapest left, reach right only when needed:

| Capability | Backend | Model | Use for |
|---|---|---|---|
| `NATIVE_SHELL` | Daemon-native bash | — | Shell, git, grep, file ops. Runs at ROME_ROOT. Free, always first choice. |
| `SAFE_SHELL` | Daemon-native bash | — | Same executor as `NATIVE_SHELL`, isolated cwd (`legions/<task_id>/`). Use when the task needs a clean working directory. |
| `GEMMA` | Ollama `localhost:11434` | `gemma4:e4b` | Cheap local triage and simple analysis. |
| `MISTRAL` | `~/projects/mistral-cli` | Mistral | Local LLM. Analysis, single-file edits. |
| `HAIKU` | `claude` CLI | `claude-haiku-4-5-20251001` | Fast cheap Claude. Triage, summaries. |
| `GEMINI` | `~/projects/gemini-cli` | `gemini-2.5-pro` (+ fallbacks) | JS/TS edits and refactors. Unreliable on non-JS/TS files — always validate output. |
| `CLAUDE` | `claude` CLI | Claude Pro default (auto-upgrades) | General backstop. Runs whatever the Pro subscription provides. |
| `OPUS` | `claude` CLI | `claude-opus-4-7` (pinned) | Architectural reasoning, novel decomposition. Explicit when Opus-grade headroom is required. |

## Setup

### Prerequisites
- **Node.js 20+**
- **Ollama** (optional) — for GEMMA and local embeddings (AAAK SemanticCache)

### Install & launch

```bash
npm install
echo "your-secure-token-here" > .rome_SOVEREIGN_TOKEN
npx tsc && bash ROME-start.sh
```

### Dispatch a task

```bash
node dist/src/client.js GEMINI "your prompt here"
```

## Direct Agent Signals (DAS)

Native agents (`src/native_agent.ts`) parse two tags from LLM output and route them through the existing WS connection:

| Tag | Action |
|---|---|
| `[ROME_SHELL: "<CMD>"]` | LLM-facing alias for `NATIVE_SHELL`. Same `runNativeShell` executor, same ROME_ROOT cwd. For use inside agent output — the Dictator dispatches `NATIVE_SHELL` directly. |
| `[ROME_DISPATCH: <CAP> "<PROMPT>"]` | Spawn sub-task via `dispatch` |

External workers and the Dictator speak the WS command protocol directly instead of using DAS tags — see `CLAUDE.md` for the full command schema.

## Configuration

- **`dictator/workers.json`** — worker capability definitions (invocation, probe, model, CLI command)
- **`dictator/config.json`** — daemon port and paths
- **`.rome_SOVEREIGN_TOKEN`** — WS auth token. Not committed.

---
**"The mesh is the medium. The Dictator decomposes; the Legions execute."**
---
