# ROME Protocol v4.0.0 Specification (Draft)

## 1. Overview: WebSocket-Native Sovereignty
ROME v4.0.0 marks the transition from an MCP-mediated framework to a sovereign, WebSocket-native ecosystem. We are eliminating the "middleman bureaucracy" of the Model Context Protocol in favor of a low-latency, full-duplex control plane.

## 2. The Death of the Middleman (MCP Deprecation)
- **The Problem:** MCP adds 300ms+ latency per request and creates "blind spots" in resource management (e.g., audio socket collisions).
- **The Solution:** Every ROME component (Dictator, Centurion, Legions) is now a **Native WS Client**. We communicate via raw JSON frames over a persistent WebSocket connection.

## 3. Persistent Legions (Long-Lived Agents)
- Transition from "Spawn-and-Die" processes to **Persistent Workers**.
- Legions (e.g., Gemini CLI) connect once and maintain an open pipe. This enables real-time interrupts, thought-streaming, and shared context persistence without re-reading files.

## 4. The "Dry, Kiss ASS" Principles
- **DRY (Don't Repeat Yourself):** One protocol (WS) for logs, tasks, and media control. No redundant JSON-RPC wrapping.
- **KISS (Keep It Simple, Stupid):** Minimize abstraction layers. Direct Shell Access (DSA) over WS commands. If it can be done in one frame, it is done in one frame.
- **ASS (Avoid Silly/Stupid Assumptions):** Zero assumptions about system state. Tools must verify existence and state via the WS feedback loop before execution.

## 5. Direct Shell Access (DSA)
Tools are no longer "abstract capabilities" registered in a secondary server. They are **direct WS commands** executed in a high-performance, isolated environment with real-time feedback.

---
**"Data without structure is noise; Protocols with middlemen are bottlenecks. ROME is the Mesh."**
