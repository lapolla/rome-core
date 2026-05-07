# ROME: Remote Orchestrated Model Execution

A distributed Agent-to-Agent Direct Signal Mesh (A2A-DSM). Peer-to-peer orchestration with real-time signal interception and autonomous sub-tasking.

## Imperial Hierarchy (Mesh)

```
[Agent A] ◀── DAS (Direct Agent Signals) ──▶ [Agent B]
    ▲                                           ▲
    └────────────── WS (Peer Protocol) ─────────┘
```

## Setup & Requirements

ROME is cross-platform (Linux/macOS) but requires a few core dependencies.

### Prerequisites
- **Node.js 20+**: Required for the Peer Server and Native Agents.
- **Python 3.11+**: Required for the Dictator daemon and Legion wrappers.
- **Ollama**: (Optional) Required for local vector embeddings (see `VECTOR_PLAN.md`).

### Quick Start (macOS)

1. **Install Dependencies**:
   ```bash
   # Using Homebrew
   brew install node python@3.11
   pip3 install -r requirements.txt
   npm install
   ```

2. **Configure**:
   Ensure you have a `.rome_SOVEREIGN_TOKEN` file in the root.
   ```bash
   echo "your-secure-token-here" > .rome_SOVEREIGN_TOKEN
   ```

3. **Launch the Mesh**:
   ```bash
   # Build TS and start the daemon
   npx tsc && bash ROME-start.sh
   ```

## Architecture

- **Peer Mesh:** Every agent is an active participant in the WebSocket-native mesh.
- **WebSocket Signal Bus:** Agents interact with the daemon via structured JSON frames over WS, providing a clean separation of control and data planes.
- **Native Agents:** `src/native_agent.ts` (TS) provides a full-duplex, real-time interaction loop for LLMs, bypassing legacy CLI wrappers.
- **Worker Hub:** Supports `native_agent` (WS-native) implementations.
- **Registry:** `src/registry.ts` tracks causal chains (goals/intents) and asynchronous state across the mesh.

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

ROME v7 supports two signaling modes:

### 1. WebSocket Signal Bus (Primary)
Agents connect to `$ROME_WS_URL` and send JSON command frames (e.g., `dispatch`, `await`, `native_shell`). See `CLAUDE.md` (WS Command Protocol section) for the full frame schema.

### 2. Regex Tags (Legacy Compatibility)
For non-WS agents, the following tags are intercepted from stdout:

| Tag | Action |
|-----|--------|
| `[ROME_DISPATCH: <CAP> "<PROMPT>"]` | Spawn sub-task |
| `[ROME_AWAIT: <TASK_ID>]` | Wait for result |
| `[ROME_READ: <PATH>]` | Read system file |
| `[ROME_SHELL: "<CMD>"]` | Execute bash |

---
**"The mesh is the medium. ROME is the mind."**
