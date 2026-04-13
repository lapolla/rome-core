# ROME: Remote Orchestrated Model Execution

A distributed Agent-to-Agent Direct Signal Mesh (A2A-DSM). Peer-to-peer orchestration with real-time signal interception and autonomous sub-tasking.

## Imperial Hierarchy (Mesh)

```
[Agent A] ◀── DAS (Direct Agent Signals) ──▶ [Agent B]
    ▲                                           ▲
    └────────────── WS (Peer Protocol) ─────────┘
```

## Architecture

- **Peer Mesh:** Every agent runs a `PeerServer` (TS), capable of hosting LLMs (GEMINI/CLAUDE) or Shell executors.
- **DAS Protocol:** Agents trigger actions via stdout tags: `[ROME_DISPATCH: ...]`, `[ROME_AWAIT: ...]`, `[ROME_SHELL: ...]`.
- **Worker Hub:** `src/legion_worker.ts` (TS) handles the real-time interception and stdio-feedback loop.
- **Registry:** `src/registry.ts` tracks causal chains (goals/intents) across the mesh.

## Configuration

ROME uses file-based configuration to enhance security and simplify setup:
- **`dictator/config.json`**: Contains daemon settings (e.g., ports, interface bindings).
- **`.rome_SOVEREIGN_TOKEN`**: Stores the secure token for WebSocket authentication. Do not commit this file.

## Quick Start

### Start the Mesh

```bash
npx tsc && bash start.sh
```

### Dispatch to the Mesh

```bash
node dist/client.js GEMINI "Write a script and run it using [ROME_SHELL: '...']"
```

## Direct Agent Signals (DAS)

| Tag | Action |
|-----|--------|
| `[ROME_DISPATCH: <CAP> "<PROMPT>"]` | Spawn sub-task |
| `[ROME_AWAIT: <TASK_ID>]` | Wait for result |
| `[ROME_READ: <PATH>]` | Read system file |
| `[ROME_SHELL: "<CMD>"]` | Execute bash |

---
**"The mesh is the medium. ROME is the mind."**
