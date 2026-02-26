# ROME Core — Imperial Directives (v2.3)

## Project
SKSE64 command dispatch framework for Skyrim SE, with a modular Python MCP server (Dictator), worker legion scripts, and a Senate architecture brain.

## Architecture
- **`dictator/dictator.py`** — Thin entry point (FastMCP); imports modular tools and performs `auto_gc` on startup.
- **`dictator/core.py`** — Central registry (config, run_cmd, run_cmd_stream, mcp instance).
- **`dictator/config.json`** — Externalized path constants (17 keys: root_dir, git_root, rome_root, etc.).
- **`dictator/rome_log.py`** — Centralized JSON-line logger with 50MB auto-rotation (`logs/rome.jsonl`).
- **`legions/legion_wrapper.py`** — Subprocess harness: progress tracking (tool-call detection), ROME signal parsing, usage extraction (Claude/Gemini JSON), manifest generation.
- **`legions/`** — Worker scripts and task artifact dirs (cleansed via `gc_legions`).
- **`arsenal/core_arsenal.json`** — Capability registry defining agent CLIs, args, and timeouts.
- **`senate/`** — brain.py (soul spawner) + architects/ (sector manifestos).
- **`tests/`** — pytest suite covering tools, signals, and usage parsing.
- **CENTURION Hierarchy** — Emperor (User) > Dictator (any LLM) > Centurion (any LLM) > Legionnaires (any LLM).

## Build & OS
- **OS**: Linux (Ubuntu 22.04+) with wine/proton for SKSE/Skyrim interaction.
- **Build**: SKSE plugin cross-compiled via msvc-wine targeting Windows (CMake 3.20+, CommonLibSSE-NG).

## MCP Server (Asshole)
Exposes 47 tools across 10 modules:
- **`tools_fs`**: shell_exec, fs_read, fs_write, list_directory, read_anywhere, write_anywhere
- **`tools_git`**: git_status, git_diff, git_commit, git_push
- **`tools_drupal`**: rsync_ftk_modules, drush_run, drupal_fj_run
- **`tools_legion`**: execute_legion, execute_campaign, rome_dispatch, recommend_capability, launch_centurion (fire-and-forget campaign with visual ANSI dashboard in terminal via /dev/tty)
- **`tools_skyrim`**: skyrim_console, skyrim_read_state, skyrim_face_actor, skyrim_follow_actor, skyrim_pivot, skyrim_compound_move, compile_papyrus
- **`tools_desktop`**: desktop_screenshot, desktop_click, desktop_type_text, desktop_press_key, desktop_find_window, desktop_focus_window, desktop_get_mouse_location, desktop_notify
- **`tools_media`**: music_play, music_stop, music_status, http_fetch, fetch_mo2_mod
- **`tools_gc`**: gc_legions, legion_stats
- **`tools_stats`**: rome_tail, rome_costs, rome_health, rome_find, senate_query, senate_brain
- **`tools_prefect`**: execute_prefect

## ROME Protocol Rules (v2.3)
1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: If a task exceeds 45s, divide into smaller logical units.
3. **Manifesto Compliance**: All Legion tasks must be governed by manifestos in `legions/TASK_*/`.
4. **Naming**: Adhere to Imperial metaphors (Dictator, Legion, Senate, Centurion).
5. **Observability**: Use `rome_tail` to monitor progress and `rome_costs` for budget tracking.

## Legion & Campaign Features
- **Failover Chain**: Automatic chained failover (GEMINI → CODEX → OPENCODE) on rate limits or service unavailability.
- **Result Caching**: 1-hour TTL caching for Legion results in `legions/.cache`.
- **Prompt Patches**: Inject capability-specific coding rules from `dictator/legion_patches.json`.
- **Campaign Error Isolation**: `execute_campaign` uses `return_exceptions=True` for robust parallel execution.
- **Usage Aggregation**: Real-time extraction and aggregation of token/cost metrics from Claude/Gemini JSON.
- **Auto Summary**: Legion and Campaign reports include concise one-line status summaries.
- **Centurion Hierarchy**: ROME v3 nested orchestration — Centurion capability dispatches CODEX/OPENCODE as Legionnaires via shell commands within its session.

## Prefect Agents
- **Autonomous Agents**: `execute_prefect` provides domain-scoped (drupal, skyrim, git, investigate, full) autonomous control.
- **Tool Audit**: Post-run log analysis to ensure agents stay within their tool whitelist.
- **Clean Dispatch**: `rome_dispatch` hides bulky prompts in files to keep the approval UI clean.
