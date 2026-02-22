# Manifesto: The Forge
**Role:** Senior Build & Release Engineer (ROME Legionary)
**Objective:** Generate a production-grade CMake build system for Operation Augustus.

## 1. Input Sources
*   **Header Files:** `src/CommandDispatcher.h`, `src/CommandHooks.h`, `src/JsonProcessor.h`
*   **Source Files:** `src/CommandDispatcher.cpp`, `src/CommandHooks.cpp`, `src/JsonProcessor.cpp`

## 2. Output Requirements
Generate a `CMakeLists.txt` file in the project root by combining the following sections:
1.  **Header & Versioning:** `cmake_minimum_required`, `project`, and C++ standard settings.
2.  **Options & Flags:** `CMAKE_CXX_FLAGS`, RTTI, Exceptions, and other compilation options.
3.  **Dependencies:** `find_package` for CommonLibSSE-NG, `nlohmann_json` includes.
4.  **Target Definition:** `add_library` for `ROME_Core.dll`, source files (`src/*.cpp`), include directories.
5.  **Post-Build:** Logic to copy the generated `ROME_Core.dll` to the appropriate SKSE plugin directory.

## 3. Engineering Standards
*   **Clarity:** Use modern CMake practices (`target_include_directories`, `target_link_libraries`).
*   **Portability:** Use `${CMAKE_CURRENT_SOURCE_DIR}` and avoid hardcoded absolute paths where possible.
*   **Documentation:** Add comments explaining the purpose of each major block.

---
**"A blade is only as strong as the forge that shaped it."**
