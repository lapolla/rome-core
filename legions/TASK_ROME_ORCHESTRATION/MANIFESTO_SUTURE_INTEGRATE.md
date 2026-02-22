# Manifesto: Tool Integration (The Suture)
**Role:** Senior Node.js Architect (ROME Legionary)
**Objective:** Unify the external toolset into the internal ROME Dictator.

## 1. Input Sources
*   Internal Dictator: `/home/paul-kane/projects/rome-core/dictator/index.mjs`
*   External Server (Extracted Tools): From TASK_SUTURE_PREP results.

## 2. Action: Integration
Merge all tools from the external server into the internal `dictator/index.mjs`. 
*   **Duplicate Handling:** If a tool name exists in both, prioritize the version from the internal Dictator unless the external one is significantly more functional.
*   **Helper Functions:** Ensure all necessary helper functions (e.g., `execAI`, `extractJSON`, `shellEscape`, `textResult`, `focusSkyrim`, etc.) are correctly migrated and integrated.
*   **Imports:** Add any missing Node.js or MCP SDK imports required by the new tools.

## 3. Output Requirements
Provide the **entire, unified content** of the new `dictator/index.mjs`. No additional text, only the code.

---
**"A unified command is a powerful command."**
