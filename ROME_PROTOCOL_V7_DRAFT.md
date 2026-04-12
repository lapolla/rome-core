# ROME Protocol v7.0.0 (DRAFT)
**Status:** DRAFT | **Focus:** Decomposer Pattern & Sovereign Blackboard

## 1. Overview: The Decomposer Layer
Building upon the Agent-to-Agent Direct Signal Mesh (A2A-DSM) established in v6, ROME v7 introduces the **Decomposer** concept. 

Crucially, the Decomposer is **NOT** a new centralized engine component or rigid code layer within the ROME daemon. Instead, it is formalized as a **Signal-Driven Pattern** and a **Specialized Agent Persona**.

## 2. The Philosophy
In alignment with the "Agent is the Orchestrator" philosophy, the Decomposer pattern dictates that for complex intents, an agent should first recursively dispatch a planning phase.

This phase takes a high-level Goal and produces a structured plan (e.g., YAML) detailing:
- **Domains:** Affected areas of the system.
- **Hypotheses:** Potential causes or approaches.
- **Probes:** Specific tests or validation steps to confirm hypotheses.
- **Outputs:** Expected results.

## 3. Execution (Plan-and-Fan)
Once the Decomposer plan is generated, the orchestrating agent dynamically parses it and translates the `probes` into real-time `[ROME_DISPATCH]` signals.

This enables:
- **Parallelized Execution (Fan-Out):** Multiple probes can be dispatched concurrently across the mesh.
- **Explicit Traceability:** The structured plan serves as an auditable "Thinking Artifact."
- **Anchored Reasoning:** Reduces LLM hallucinations and thrashing by forcing commitment to a logical chain before acting.

## 4. Avoiding Rigidity
To maintain the fluidity of the mesh and adhere to the KISS principle:
- The Decomposer pattern should be bypassed for trivial tasks to avoid latency overhead.
- Agents must remain adaptable; if live system feedback from a probe contradicts the initial hypothesis, the agent can discard the plan and revert to iterative `[ROME_SHELL]` execution.

## 5. The Sovereign Blackboard (Distributed State)
ROME v7 evolves from a "Log of Tasks" to a **Sovereign State Machine**. This provides agents with a unified, queryable source of truth.

### 5.1 Protocol: RSB over DAS
State management moves from legacy stdout tags (DAS) to the **ROME Signal Bus (RSB)**. Agents interact with state via structured JSON commands over their persistent WebSocket connection:
- `state_set`: Update a global state variable with causal metadata (e.g., `caused_by_task`).
- `state_get`: Explicitly query a slice of the state tree.

### 5.2 The Mesh Reducer
The ROME daemon implements a deterministic **Mesh Reducer** that transforms raw mesh events into state transitions:
1. **Intercept:** Detects `task_completed` events.
2. **Reduce:** Maps JSON report payloads to state patches based on predefined schemas.
3. **Link:** Automatically binds updates to the triggering `task_id` for perfect causal auditability.

### 5.3 Architecture: Centralized Memory, Distributed Access
To maintain the **ROME KISS mandate**, the state object (the Blackboard) is held in the daemon’s memory. Distributing state via consensus protocols (like Raft) is avoided to minimize complexity and latency. Centralization ensures atomic writes and immediate consistency for the ephemeral mesh.

### 5.4 The "Context Diet" Win
- **Massive context savings:** Agents query a specific JSON state object instead of parsing megabytes of historical task logs.
- **Decoupled Orchestration:** Specialized agents can be spawned to react to specific state changes (e.g., `build_status: FAILED`), perform a fix, and exit without needing full session history.

## 6. Architectural Findings & Constraints (Addendum)

### 6.1 The Real Breakpoint: From Logs to State
ROME v7 marks a fundamental shift: The system no longer operates on historical logs, but on a deterministic, queryable state.
- **v6:** event-driven + implicit state (logs)
- **v7:** event → reducer → explicit state

This transition eliminates dependency on context replay, enables stateless agents, and allows deterministic system reasoning.

### 6.2 The Mesh Reducer as the Core Authority
The Mesh Reducer is the most critical component in v7.
- **Responsibilities:** Transform events into state transitions, enforce determinism, and maintain causal linkage (`caused_by_task`).
- **Design constraint:** The reducer MUST remain simple, explicit, and deterministic.
- **Anti-patterns:** Implicit inference inside reducer, LLM-assisted state mutation, and non-reproducible transformations.

### 6.3 State as Source of Truth (Not Memory)
The Sovereign Blackboard is authoritative system state, not historical memory.
- **Implications:** Agents MUST prefer `state_get` over log parsing. Memory-like systems (e.g., summaries) are advisory only. All execution-critical data must be represented as state.

### 6.4 Decomposer as a Behavioral Pattern
The Decomposer is a signal-driven planning behavior, not a system component.
- **Constraints:** Must be optional (bypassed for trivial tasks), must not introduce mandatory latency, and must remain interruptible and discardable.
- **Execution model:** `plan → fan-out → observe → mutate plan`

### 6.5 Controlled Fan-Out
Unbounded decomposition leads to instability.
- **Required controls:** Max parallel probes, bounded hypothesis set, and killable branches (active / killed / confirmed).

### 6.6 Deterministic Execution over Implicit Intelligence
ROME v7 favors explicit structure over implicit reasoning. Plans are auditable artifacts, probes are explicit questions, and state transitions are reproducible. This reduces hallucination and improves debuggability.

### 6.7 Centralized State Tradeoff
The Blackboard is intentionally centralized.
- **Pros:** Atomic updates, immediate consistency, minimal latency.
- **Cons:** Single point of failure.
- **Decision:** Acceptable for ephemeral mesh execution environments.

### 6.8 Context Elimination Strategy
ROME v7 minimizes LLM context usage by design. Agents query structured state instead of replaying history, and tasks operate on current truth, not narrative.
- **Result:** Massive token reduction and improved reliability.

### 6.9 System Identity
ROME v7 should be understood as: **An event-driven distributed state machine with LLM-based reasoning interfaces.**
It is NOT a memory system or a chat-based agent framework.

### 6.10 Future Constraints (Non-Goals for v7)
To preserve system integrity:
- No distributed consensus (e.g., Raft).
- No implicit memory injection.
- No reducer-side intelligence.

### 6.11 Concurrency & Conflict Resolution
To handle parallel `state_set` collisions:
- **Optimistic Concurrency:** The daemon should prioritize updates from the most recently dispatched task in a causal chain.
- **Atomic Patching:** State updates must use targeted key-value patches (or JSON Patch) rather than full object overwrites to prevent accidental data loss.

---
**TL;DR (Internal)**
- **Decomposer** = thinking pattern
- **Mesh** = execution layer
- **Reducer** = truth engine
- **State** = system reality
