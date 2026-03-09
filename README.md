# 🏛️ ROME: Remote Orchestrated Model Execution

*“Veni, Vidi, Vici — Through Parallel Legionnaires.”*

ROME is a high-performance **MCP (Model Context Protocol) orchestration framework** designed to provide unified, scalable, and failover-capable model execution. In the ROME ecosystem, the user is the **Emperor**, commanding a **Dictator** (any LLM agent) who in turn dispatches **Legions** of specialized workers to conquer complex tasks.

## 👑 The Imperial Hierarchy

1.  **Emperor (You):** The ultimate authority. You provide high-level objectives and oversee the campaign.
2.  **Dictator (LLM Agent):** Appointed by the Emperor to manage the campaign. The Dictator is model-agnostic (Claude, GPT-4, etc.) and interprets goals into actionable commands for the Legions.
3.  **Legions (Workers):** Expendable, specialized AI agents dispatched in parallel.
    *   **GEMINI:** High-speed generalist coding and analysis.
    *   **CODEX:** Specialized code manipulation and repository insight.
    *   **OPENCODE:** Local/OSS model execution for privacy-sensitive tasks.

## ⚔️ The Arsenal (47 MCP Tools)

ROME provides 10 specialized modules containing 47 powerful tools to dominate any digital domain:

*   📁 **Filesystem:** Advanced file manipulation and directory management.
*   🌿 **Git:** Deep repository integration and automated source control.
*   💧 **Drupal:** Specialized CMS orchestration and site management.
*   🐲 **Skyrim Interaction:** Automated state reading and console-based control.
*   🖥️ **Desktop Automation:** Direct interaction with host OS and applications.
*   🎬 **Media:** Sophisticated media processing and transformation.
*   🛡️ **Legion Orchestration:** Management of worker state and lifecycle.
*   🚩 **Campaign Execution:** Advanced task scheduling and parallel processing.
*   🏛️ **Senate:** Architecture brain utilizing sector manifestos for domain expertise.
*   ⚖️ **Prefect:** Domain-scoped autonomous agents (Drupal, Skyrim, Git, Investigate, Full).

## 🎖️ Key Features

### 🚜 Centurion CLI
A standalone visual ANSI dashboard for real-time campaign execution. Monitor multiple parallel legions with dedicated progress bars and live status updates.

### 🚩 Campaign System
A robust execution engine for parallel tasks with **DAG (Directed Acyclic Graph)** dependency management.
*   **Failover Chains:** Automatic fallback (e.g., GEMINI → CODEX → OPENCODE) ensure reliability even when individual models fail.
*   **Result Caching:** Intelligent persistence to prevent redundant compute and minimize API latency.

### 🏛️ The Senate & Sector Manifestos
The architectural brain of ROME. The Senate maintains domain-specific "manifestos" that guide Legions with deep, specialized knowledge of each project sector.

### ⚖️ Prefect Agents
Autonomous, specialized agents designed for surgical precision in specific domains (Drupal, Skyrim, Git, and full-system investigation).

## 🚀 Quick Start

Initialize the ROME server to start your conquest.

### Configuration
Ensure your environment is configured before deployment:
*   **Main Configuration:** `dictator/config.json`
*   **Arsenal Definitions:** `arsenal/core_arsenal.json`

### Starting the MCP Server
The server entry point is managed by the Dictator:
```bash
python3 dictator/dictator.py
```

---
*Glory to Rome. Efficiency to the Empire.*
