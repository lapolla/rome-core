# ROME v7 Implementation Plan (The Sovereign Mesh)

This document outlines the phased migration from the v6 "Task Log" model to the v7 "Sovereign State Machine" architecture.

## Phase 1: The Sovereign Blackboard (Infrastructure)
*   **Target:** `src/registry.ts`
*   **Objective:** Create a centralized, authoritative state store in the daemon.
*   **Tasks:**
    *   Implement `Blackboard` class with support for key-value storage.
    *   Add support for atomic JSON patching.
    *   Implement causal tracking (`caused_by_task` metadata).
    *   **TDD:** Unit tests for concurrent state updates and optimistic concurrency resolution.

## Phase 2: RSB Protocol Expansion (Communication)
*   **Target:** `src/peer_server.ts`
*   **Objective:** Enable agents to query and mutate state via the ROME Signal Bus.
*   **Tasks:**
    *   Implement `state_set` command handler.
    *   Implement `state_get` command handler.
    *   Add RSB authorization guards for state access.
    *   **TDD:** Protocol integration tests for state retrieval and updates.

## Phase 3: The Mesh Reducer (Automation)
*   **Target:** `src/peer_server.ts` / `src/registry.ts`
*   **Objective:** Automatically transform mesh events into state transitions.
*   **Tasks:**
    *   Implement deterministic `Reducer` logic.
    *   Map `task_completed` reports to state patches based on predefined schemas.
    *   Ensure strict determinism (no LLM logic inside the reducer).
    *   **TDD:** End-to-end tests verifying state transitions triggered by task completion.

## Phase 4: State-Aware Dashboard (Visualization)
*   **Target:** `dashboard/index.html`
*   **Objective:** Provide real-time visibility into the Sovereign Blackboard.
*   **Tasks:**
    *   Add a "Sovereign State" UI panel.
    *   Broadcast `state_changed` events from the daemon to the dashboard.
    *   Visualize causal links (connecting state variables to the tasks that set them).

## Phase 5: The Decomposer Persona (Orchestration)
*   **Target:** `arsenal/core_arsenal.json` / System Prompts
*   **Objective:** Formalize the planning behavior defined in the v7 spec.
*   **Tasks:**
    *   Draft the Decomposer system prompt (YAML-driven planning).
    *   Integrate the "Plan-and-Fan" loop into the primary agent persona.
    *   Verify recursive dispatch using the new state system for context reduction.
