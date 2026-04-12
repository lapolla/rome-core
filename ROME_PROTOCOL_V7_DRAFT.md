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
