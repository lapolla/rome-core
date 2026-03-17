# Design Document: ROME MCP Tools WS-Only Migration

## 1. Introduction

The objective of this document is to outline a migration strategy to consolidate ROME's extensive set of Message Control Protocol (MCP) tools into a WebSocket (WS)-only communication model, specifically by routing all tool calls through a single `ws_send` mechanism. This initiative aims to streamline the tool invocation process, centralize command execution, and enhance the overall architecture by leveraging a unified, event-driven communication channel. The ultimate goal is to reduce the current proliferation of distinct MCP tools (currently ~50) to a singular, versatile `ws_send` interface.

## 2. Categorization of Existing Tools

Based on a comprehensive analysis of the `tools_*.py` modules in `/home/paul-kane/projects/rome-core/dictator/`, existing MCP tools can be broadly categorized into two groups concerning their migration effort: "Trivial Conversion" and "Special Handling Required."

### 2.1. Trivial Conversion Candidates

These tools typically wrap a single shell command, perform basic file I/O, or execute self-contained Python logic without complex state management or external orchestration beyond a direct call-and-response. Their parameters can be directly mapped to a WebSocket payload, and the corresponding operation can be executed by the WebSocket server.

**Examples:**

*   **`tools_desktop.py` (all functions: `desktop_screenshot`, `desktop_click`, `desktop_type_text`, `desktop_press_key`, `desktop_find_window`, `desktop_focus_window`, `desktop_get_mouse_location`, `desktop_notify`)**: These are direct wrappers around `xdotool`, `scrot`, or `notify-send` shell commands.
*   **`tools_drupal.py` (`drush_run`)**: A straightforward wrapper for `composer exec drush`.
*   **`tools_fs.py` (`fs_read`, `fs_write`, `read_anywhere`, `write_anywhere`, `list_directory`)**: Basic file system operations that can be directly executed by the WS server. `shell_exec`'s base command execution is trivial, but its streaming nature needs consideration.
*   **`tools_gc.py` (`reset_tasks`, `clear_cache`)**: `reset_tasks` already uses WS, `clear_cache` is a simple file deletion.
*   **`tools_git.py` (all functions: `git_status`, `git_diff`, `git_commit`, `git_push`)**: Direct wrappers around `git` shell commands.
*   **`tools_media.py` (`http_fetch` (download part only), `fetch_mo2_mod`)**: Primarily `wget` wrappers for file downloads.
*   **`tools_legion.py` (`clear_cache`, `recommend_capability`)**: Simple cache clearing and self-contained recommendation logic.
*   **`tools_skyrim.py` (`skyrim_read_state`, `compile_papyrus`)**: File I/O for game state and a shell script wrapper for compilation.

### 2.2. Special Handling Required

These tools exhibit greater complexity, involving multi-step processes, intricate internal logic, management of external processes (including background tasks), manipulation of environment variables, direct desktop interaction, or deep integration with ROME's task orchestration and event system. Migrating these will necessitate careful re-architecture, potentially breaking them down into simpler WS commands or re-implementing their logic directly within the WS server.

**Examples:**

*   **`tools_docs.py` (`update_project_docs`)**: Performs file system reads (multiple manifests), regex processing, and writes to multiple documentation files, encapsulating significant business logic.
*   **`tools_drupal.py` (`rsync_ftk_modules`, `drupal_fj_run`)**: `rsync_ftk_modules` involves `rsync` with specific paths. `drupal_fj_run` orchestrates web drivers, manages environment variables, and executes `phpunit`, including starting background processes.
*   **`tools_fs.py` (`shell_exec` - streaming aspects)**: While core execution is simple, the streaming output, truncation logic, and custom error formatting would need careful translation to a WS message flow.
*   **`tools_gc.py` (`gc_legions`, `legion_stats`)**: `gc_legions` involves filesystem traversal and deletion logic. `legion_stats` performs log file parsing, time-based filtering, JSON deserialization, and aggregation.
*   **`tools_media.py` (`http_fetch` - extraction part)**: Contains conditional logic for different archive types and uses various external extraction tools.
*   **`tools_legion.py` (`execute_legion`, `execute_campaign`, `rome_dispatch`, `launch_centurion`)**: These are core orchestration and execution tools. `execute_legion` manages caching, fallback chains, retries, input file staging, prompt patching, event emission, and subprocesses. `execute_campaign` adds parallel execution, dependency management, and real-time UI updates. `rome_dispatch` offers hybrid blocking/non-blocking behavior. `launch_centurion` launches a separate CLI dashboard process.
*   **`tools_prefect.py` (`execute_prefect`)**: Orchestrates `_execute_legion_impl` with domain-specific context, config reading, prompt generation, and post-execution auditing.
*   **`tools_skyrim.py` (`skyrim_console`, `skyrim_face_actor`, `skyrim_follow_actor`, `skyrim_pivot`, `skyrim_compound_move`)**: These tools directly interact with the desktop environment (`xdotool`) to control application windows and input, requiring a fundamental re-evaluation of how such interactions are managed in a WS-only model.
*   **`tools_stats.py` (all functions: `rome_tail`, `rome_costs`, `rome_health`, `rome_find`, `senate_query`, `senate_brain`)**: These tools involve complex logic for log parsing, aggregation, health checks (including HTTP requests and shell commands), extensive file system traversal and searching, and orchestration with `_execute_legion_impl`.

## 3. Migration Strategy

The migration will proceed in phases, prioritizing trivial conversions and then tackling more complex tools with a re-architected approach.

### 3.1. Trivial Tools: Direct WS Command Mapping

For tools categorized as "Trivial Conversion Candidates," the migration will involve:

1.  **Defining WS Command Payloads:** Each trivial MCP tool will have a corresponding WS command. The existing tool's function signature (parameters) will directly inform the structure of the WS command's JSON payload.
2.  **WS Server Implementation:** The ROME Daemon's WebSocket server will be extended to recognize and handle these new commands. The server-side logic for each command will largely mirror the original Python implementation, executing the shell command or Python function with the provided payload arguments.
3.  **Client-Side Replacement:** The original `mcp.tool()` registrations in `tools_*.py` will be removed. Calls to these tools will be replaced with calls to `ws_send`, passing the command name and the corresponding payload.

**Example for `desktop_screenshot`:**

*   **Old MCP Tool Call:** `await mcp.tool.desktop_screenshot(window_id="some_id")`
*   **New WS Command Call:** `await ws_send("desktop_screenshot", {"window_id": "some_id"})`
*   **WS Server Handling:** The WS server receives `{"command": "desktop_screenshot", "payload": {"window_id": "some_id"}}`, then executes `scrot` or `xdotool` as appropriate and returns the result.

### 3.2. Complex Tools: Re-architecture and Decomposition

Tools requiring "Special Handling" will undergo a more significant re-architecture:

1.  **Logic Re-implementation in WS Server:** For tools with substantial internal Python logic (e.g., `update_project_docs`, `gc_legions`, `legion_stats`, `rome_tail`, `rome_costs`, `rome_find`, `senate_query`), their core functionalities will be moved and re-implemented directly within the WS server. This centralizes the logic and removes the dependency on the `dictator` module for these operations.
2.  **Decomposition into Smaller WS Commands:** Complex tools (e.g., `drupal_fj_run`, `execute_legion`, `execute_campaign`, `execute_prefect`) will be broken down. Their constituent steps or sub-operations will be exposed as smaller, atomic WS commands. The orchestration logic that combines these steps will reside either on the client (the calling agent) or as a new, higher-level WS command on the server.
3.  **Rethinking Desktop Interaction:** Tools like `skyrim_console` and desktop automation tools from `tools_desktop.py` (if the desktop interaction cannot be simplified to trivial shell commands) pose a challenge. A dedicated "desktop agent" or "headless X server" might be necessary on the server-side, offering a WS interface to control a virtual or physical display. Alternatively, the client (the agent running the tool) would need to retain specific local capabilities for these interactions. However, given the goal of a WS-only model, the former is preferred.
4.  **Leveraging Existing WS Capabilities:** `rome_dispatch` already dispatches tasks via WS for fire-and-forget scenarios. This pattern will be generalized, and `_execute_legion_impl`'s internal logic will be integrated into the WS server as a set of callable primitives. The `rome_await` tool will become crucial for blocking on the completion of asynchronous tasks initiated via `ws_send`.
5.  **Streaming Output for `shell_exec`:** The streaming nature of `shell_exec` will require a WS command that can send continuous updates (e.g., lines of output) back to the client, possibly through a dedicated event stream or by structuring the WS response as a sequence of partial results.
6.  **Environment and Subprocess Management:** The WS server will be responsible for managing environment variables and spawning subprocesses for tools like `drupal_fj_run` and `launch_centurion`. This centralizes the execution context.

## 4. Backward Compatibility Plan

The migration will aim for a phased deprecation rather than an abrupt cutover to minimize disruption.

1.  **Parallel Tool Registration (Transition Period):** For a transition period, both the old `mcp.tool()` registrations and the new `ws_send` calls for the same functionality could coexist. This would allow agents to gradually migrate their tool usage.
2.  **Deprecation Warnings:** As tools are migrated to the WS-only model, the original `mcp.tool()` implementations will be updated to issue deprecation warnings when invoked, guiding users towards the new `ws_send` interface.
3.  **Clear Documentation:** Comprehensive documentation will be provided, detailing the new WS commands, their payloads, and how to migrate existing tool calls.
4.  **Removal of Legacy Tools:** After a defined deprecation period and sufficient migration by agents, the old `mcp.tool()` registrations and their underlying implementations will be removed.
5.  **API Versioning:** For future evolutions, consider implementing API versioning for the WebSocket interface to manage changes gracefully.

By following this strategy, ROME can achieve a cleaner, more maintainable, and unified tool invocation architecture while ensuring a manageable transition for existing agents and functionalities.