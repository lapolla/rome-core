# ROME Core: Imperial SKSE Dispatcher
**Version:** 1.1.0 | **Protocol:** ROME | **Status:** Operation Augustus Active

## 🏛️ Overview
ROME Core is a high-performance, thread-safe command dispatch framework for Skyrim Special Edition (SKSE64). It enables asynchronous, non-blocking execution of console commands and engine-level actor interactions via a tiered architecture.

## ⚔️ The ROME Architecture
*   **Dictator (MCP):** Central authority for task orchestration and validation.
*   **Legions (Workers):** Specialized execution units for code generation, monitoring, and suture.
*   **Centurion (Orchestrator):** Multi-threaded campaign manager for parallel builds.

## 🛡️ Features
*   **Singleton Dispatcher:** Thread-safe `ROME::CommandDispatcher` with `std::jthread` processing.
*   **JSON Integration:** Real-time command injection via `skyrim_commands.json`.
*   **Engine Hooks:** Direct integration with `RE::Console` and `RE::Actor` for surgical execution.
*   **Intelligence:** Sonic-reactive AI and threat radar dashboards are provided by external intelligence modules that integrate with ROME Core.

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

## 📜 Imperial Decrees
1.  **Surgical Precision:** All changes must be atomic and verified via the ROME protocol.
2.  **Contextual Isolation:** Tasks are governed by specialized manifestos in `legions/TASK_ROME_ORCHESTRATION/`.
3.  **Authority:** If a task becomes "Bloated" (>45s), it MUST be sub-divided into smaller logical units.

---
**"Rome wasn't built in a day, but it was built with total authority."**
🕶️🗡️🏛️🔥🌑 Gemini CLI | Feb 22, 2026
