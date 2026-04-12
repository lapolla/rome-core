# ROME: Remote Orchestrated Model Execution (v6.0.0)

A distributed Agent-to-Agent Direct Signal Mesh (A2A-DSM). Peer-to-peer orchestration with real-time signal interception and autonomous sub-tasking.

## Imperial Hierarchy (Mesh)

```
[Agent A] ◀── DAS (Direct Agent Signals) ──▶ [Agent B]
    ▲                                           ▲
    └────────────── WS (Peer Protocol) ─────────┘
```

## Architecture (v6)

- **Peer Mesh:** Every agent runs a `PeerServer` (TS), capable of hosting LLMs (GEMINI/CLAUDE) or Shell executors.
- **DAS Protocol:** Agents trigger actions via stdout tags: `[ROME_DISPATCH: ...]`, `[ROME_AWAIT: ...]`, `[ROME_SHELL: ...]`.
- **Worker Hub:** `src/legion_worker.ts` (TS) handles the real-time interception and stdio-feedback loop.
- **Registry:** `src/registry.ts` tracks causal chains (goals/intents) across the mesh.

## Quick Start

### Start the Mesh

```bash
npx tsc && bash v6-start.sh
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
