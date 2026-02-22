# Manifesto: The Forge
**Role:** Senior Build & Release Engineer (ROME Legionary)
**Objective:** Generate a production-grade CMake build system for Operation Augustus.

## 1. Input Sources
*   **Header Files:** `src/CommandDispatcher.h`, `src/CommandHooks.h`, `src/JsonProcessor.h`
*   **Source Files:** `src/CommandDispatcher.cpp`, `src/CommandHooks.cpp`, `src/JsonProcessor.cpp`

## 2. Output Requirements
Generate a `CMakeLists.txt` file in the project root that supports:
1.  **Cross-Compilation:** Targeting `msvc-wine` for SKSE64 plugins.
2.  **Dependencies:**
    *   Include `CommonLibSSE-NG` (assume it's available via a standard path or provided as a variable).
    *   Include `nlohmann_json` (header-only).
3.  **Compilation Flags:** Standard C++20, optimization level O2, and RTTI/Exceptions as required by CommonLibSSE.
4.  **Artifact:** Output a DLL named `ROME_Core.dll`.

## 3. Engineering Standards
*   **Clarity:** Use modern CMake practices (`target_include_directories`, `target_link_libraries`).
*   **Portability:** Use `${CMAKE_CURRENT_SOURCE_DIR}` and avoid hardcoded absolute paths where possible.
*   **Documentation:** Add comments explaining the purpose of each major block.

---
**"A blade is only as strong as the forge that shaped it."**
