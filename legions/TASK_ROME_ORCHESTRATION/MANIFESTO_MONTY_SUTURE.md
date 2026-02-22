# Manifesto: The Pythonic Suture
**Role:** Senior Python Systems Engineer (ROME Legionary)
**Objective:** Port the complete toolset to `dictator/dictator.py`.

## 1. Input Sources
*   Recovered Tool logic: `/home/paul-kane/tmp/augustus_slave_TASK_MONTY_*/report_*.txt`

## 2. Output Requirements
Provide the **entire, unified content** of `dictator/dictator.py`. 
It MUST include:
1.  **Imports:** `sys`, `json`, `os`, `subprocess`, `time`, `pathlib`, `shutil`.
2.  **Protocol Loop:** Robust stdio JSON-RPC (initialize, listTools, callTool).
3.  **Tool Implementations:** All 50+ tools ported from the reports.
4.  **Helper Functions:** `text_result`, `focus_skyrim`, `calibrate_mouse`, etc.

## 3. Engineering Standards
*   Use `subprocess.run` or `subprocess.check_output` for system calls.
*   Implement `list_directory` using `pathlib.Path.rglob` or `iterdir`.
*   Ensure all tools return the MCP-compliant `{"content": [...]}` structure.

---
**"Structure is the foundation of authority. Python is the sword."**
