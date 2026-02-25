# ROME Core: Imperial SKSE Dispatcher
**Version:** 2.0.0 | **Protocol:** ROME v2.0 | **Status:** Operation Augustus Active

## Overview
ROME Core is a high-performance, thread-safe command dispatch framework for Skyrim Special Edition (SKSE64). It enables asynchronous, non-blocking execution of console commands and engine-level actor interactions via a tiered architecture.

## The ROME Architecture
*   **Dictator (MCP):** Python MCP server — central authority for task orchestration, validation, and usage tracking.
*   **Legions (Workers):** Specialized execution units (Gemini, Claude, Codex, SAFE_SHELL) managed by `legion_wrapper.py`.
*   **Arsenal:** Capability registry (`arsenal/core_arsenal.json`) defining agent CLIs, args, and timeouts.
*   **Centurion (Orchestrator):** Campaign manager for parallel task execution with usage aggregation.

## Features
*   **Singleton Dispatcher:** Thread-safe `ROME::CommandDispatcher` with `std::jthread` processing.
*   **JSON Integration:** Real-time command injection via `skyrim_commands.json`.
*   **Engine Hooks:** Direct integration with `RE::Console` and `RE::Actor` for surgical execution.
*   **Usage Tracking:** Per-task and per-campaign token/cost reporting from agent CLIs.
*   **Progress Reporting:** Real-time heartbeat progress via `progress.log` and manifest `progress` array.

## 🛠️ Build & Deploy
This project uses a specialized `msvc-wine` cross-compilation pipeline.

### Prerequisites
*   CMake 3.20+
*   CommonLibSSE-NG
*   nlohmann/json
*   **MSVC-Wine Toolchain:** A configured cross-compilation environment (e.g., using `msvc-wine` or `MinGW-w64`) targeting Windows for SKSE64. Specific setup instructions for this environment are outside the scope of this README but are assumed to be present.

### Compilation
```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make
```

## Project Layout
```
src/              C++ SKSE plugin (CommandDispatcher, JsonProcessor, CommandHooks)
dictator/         Python MCP server (dictator.py, rome_log.py, config.json)
legions/          legion_wrapper.py + worker scripts + task artifact dirs
arsenal/          core_arsenal.json — capability registry
senate/           Architecture brain + sector manifestos
tests/            pytest suite (test_dictator.py — 18 tests)
logs/             rome.jsonl — structured event log with usage data
```

## 📜 Imperial Decrees
1.  **Surgical Precision:** All changes must be atomic and verified via the ROME protocol.
2.  **Contextual Isolation:** Tasks are governed by specialized manifestos in `legions/TASK_ROME_ORCHESTRATION/`.
3.  **Authority:** If a task becomes "Bloated" (>45s), it MUST be sub-divided into smaller logical units.

---
**"Rome wasn't built in a day, but it was built with total authority."**
