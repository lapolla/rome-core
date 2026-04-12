# ROME Protocol v7.0.0 (DRAFT)
**Status:** DRAFT | **Focus:** The Decomposer Pattern

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
