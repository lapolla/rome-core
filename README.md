# ROME: Remote Orchestrated Model Execution

A WebSocket-native orchestration mesh. Dictator decomposes goals; Legions
(LLM workers) execute via the daemon over `ws://127.0.0.1:8741`.

## Architecture

- **`src/peer_server.ts`** — WS daemon. Routes dispatch, tracks tasks, broadcasts events.
- **`src/native_agent.ts`** — Full-duplex native agent. Connects directly to Ollama / external LLMs; intercepts DAS signals (`[ROME_SHELL:]`, `[ROME_DISPATCH:]`) from model output.
- **`src/shell_executor.ts`** — Dedicated bash executor for `SAFE_SHELL`.
- **`src/registry.ts`** — `EventBus`, `TaskRegistry`, `WorkerRegistry`.
- **`src/client.ts`** — Headless CLI dispatcher.
- **`ROME-start.sh`** — Mesh launcher.

See **`CLAUDE.md`** for the full WS command schema and protocol rules.

## ⚡ Every Worker is a Mesh Node

**This is the property that bites you if you forget it.**

Every worker spawned by `native_agent_cli` — CLAUDE, OPUS, HAIKU, GEMINI, MISTRAL — connects back to `ws://127.0.0.1:8741` on spawn. Workers are **not** isolated subprocesses returning text. They are full mesh participants: they can sub-dispatch, read/write blackboard state, emit progress events, and receive cancellation signals — all over the same WS connection.

**Implications:**
- A CLAUDE/OPUS worker that dispatches further is a recursive Dictator inside the mesh. It inherits all parent constraints. If GEMINI is fenced, a sub-dispatch from inside that worker hits the same fence — and fails silently.
- Progress events stream to the bus in real time. No polling needed.
- Sub-tasks dispatched from inside a worker appear in the registry alongside parent tasks. The mesh is always deeper than one level.

## Setup

### Prerequisites
- **Node.js 20+**
- **Ollama** (optional) — for local embeddings used by AAAK / SemanticCache.

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

Native agents (`src/native_agent.ts`) parse two tags from LLM output and
execute them through the existing WS connection:

| Tag | Action |
|-----|--------|
| `[ROME_SHELL: "<CMD>"]` | Run shell via `native_shell` |
| `[ROME_DISPATCH: <CAP> "<PROMPT>"]` | Spawn sub-task via `dispatch` |

CLI/external workers can speak the WS command protocol directly instead
of using DAS tags — see `CLAUDE.md` for the 17-command schema.

## Configuration

- **`dictator/config.json`** — daemon port + paths.
- **`.rome_SOVEREIGN_TOKEN`** — WS auth token. Not committed.
- **`arsenal/core_arsenal.json`** — capability definitions (CLI, args, model).

---
**"The mesh is the medium. ROME is the mind."**
