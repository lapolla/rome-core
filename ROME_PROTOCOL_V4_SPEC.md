# ROME Protocol v4.0.0 Specification
**Status:** ACTIVE | **Authority:** Absolute | **Version:** 4.0.0

## 1. Overview: WebSocket-Native Sovereignty
ROME v4.0.0 marks the transition from an MCP-mediated framework to a sovereign, WebSocket-native ecosystem. We have eliminated the "middleman bureaucracy" of the Model Context Protocol in favor of a low-latency, full-duplex control plane.

## 2. The Death of the Middleman (MCP Deprecation)
- **The Problem:** MCP adds 300ms+ latency per request and creates "blind spots" in resource management (e.g., audio socket collisions).
- **The Solution:** Every ROME component (Dictator, Centurion, Legions) is now a **Native WS Client**. We communicate via raw JSON frames over a persistent WebSocket connection on port 8741.

## 3. Persistent Legions (Long-Lived Agents)
- **Implementation:** Legions (e.g., Gemini CLI) now connect once and maintain an open pipe using `legion_wrapper.py --mode worker`.
- **Handshake:** Uses a `daemon_hello` -> `agent_hello` sequence to negotiate capabilities and assign unique `worker_id`s.
- **Benefits:** Eliminates the 2-5s process startup overhead. Enables real-time thought-streaming and shared context persistence.
- **Status:** GEMINI and SAFE_SHELL workers are live and resident in memory.

## 4. The "Dry, Kiss ASS" Principles
- **DRY (Don't Repeat Yourself):** One protocol (WS) for logs, tasks, and media control.
- **KISS (Keep It Simple, Stupid):** Minimize abstraction layers. Direct Shell Access (DSA) over WS commands.
- **ASS (Avoid Silly/Stupid Assumptions):** Zero assumptions about system state. Tools verify existence and state via the WS feedback loop before execution.

## 5. Direct Shell Access (DSA)
- **`NATIVE_SHELL` Capability:** Executes commands directly within the ROME Daemon's environment.
- **Latency:** Sub-millisecond execution overhead (~2ms total task lifecycle).
- **Command:** `{"command": "native_shell", "payload": {"command": "..."}}`

## 6. Real-Time Interrupts & Steering
- **`interrupt` Command:** Allows the Dictator to cancel tasks or steer persistent workers mid-execution.
- **Targeting:** Supports targeting by `task_id` or `worker_id`.

---
**"Data without structure is noise; Protocols with middlemen are bottlenecks. ROME is the Mesh."**
