# ROME Protocol v2.0 Specification
**Status:** DRAFT | **Authority:** Absolute | **Version:** 2.0.0

## 1. Overview
The ROME (Remote Orchestrated Model Execution) Protocol v2.0 transitions from unstructured text concatenation to a structured, dependency-aware artifact management system. It introduces the "ROME Signal" for model-to-orchestrator communication and a mandatory "Manifest" for all task outputs.

## 2. The ROME Signal
Models MUST use specialized tags to demarcate their primary output and provide metadata to the `legion_wrapper`.

*   **`[ROME_START]` / `[ROME_END]`**: Wraps the primary code or text artifact.
*   **`[ROME_META: key=value]`**: Injects metadata directly into the task's `manifest.json`.
*   **`[ROME_STATUS: SUCCESS|FAILED|RETRY]`**: Explicitly sets the task outcome.

## 3. The Task Manifest (`manifest.json`)
Every task execution MUST produce a `manifest.json` in its sandbox directory.

```json
{
  "rome_v": "2.0",
  "task_id": "TASK_ID",
  "status": "SUCCESS",
  "metadata": {
    "key": "value"
  },
  "usage": {
    "model": "gemini-2.5-flash",
    "input_tokens": 3486,
    "output_tokens": 27,
    "total_tokens": 3643,
    "cost_usd": null
  },
  "progress": [
    "0% + [0.0s] Engaged (V2.0).",
    "20% x [1.2s] Reasoning...",
    "100% * [8.3s] Mission complete."
  ],
  "artifacts": [
    {
      "path": "report_TASK_ID.txt",
      "type": "extracted|raw"
    }
  ],
  "runtime": {
    "elapsed_s": 12.5,
    "exit_code": 0
  }
}
```

## 4. Dependency-Aware Orchestration (DAG)
Tasks in a campaign can now define dependencies. The Orchestrator (`centurion_v2`) will only execute a task when all its `depends_on` requirements are met with a `SUCCESS` status.

## 5. Structured Suture (Suture v3.0)
The Suture capability no longer performs simple concatenation. It:
1.  Collects all `manifest.json` files from a campaign.
2.  Validates exported symbols and file paths.
3.  Uses a "Blueprint" template to inject artifacts into their final destination files.
4.  Resolves naming collisions and ensures correct logic ordering.

## 6. Slave Roles (v2.0)
*   **GEMINI (Senate/Architect):** High-level logic, complex Python, and Suture consolidation.
*   **CLAUDE (Security/Review):** Code review, security audits, and edge-case detection.
*   **OPENCODE (I/O Slave):** File system operations, shell scripting, and boilerplate generation.
*   **CODEX (Test Slave):** Unit test generation and verification.
*   **SAFE_SHELL:** Direct bash command execution via legion_wrapper (60s timeout).

## 7. Usage Tracking
Agent CLIs that support `--output-format json` (Claude, Gemini) emit structured usage data. The `legion_wrapper` extracts this via `parse_usage()` and writes it to the manifest. Non-JSON agents (Codex, SAFE_SHELL) produce `usage: null`.

The Dictator aggregates usage across campaigns via `total_usage` in `execute_campaign()` responses.

## 8. Progress Reporting
The `LegionaryUI` in `legion_wrapper.py` emits heartbeat progress lines during execution:
- Written to `progress.log` in the task directory (real-time tailable)
- Stored in manifest under `"progress"` array
- Surfaced by `execute_legion()` in its structured JSON return

---
**"Data without structure is noise; structure without authority is chaos."**
