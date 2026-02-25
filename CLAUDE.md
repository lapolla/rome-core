# ROME Core — Imperial Directives

## Project
SKSE64 command dispatch framework for Skyrim SE, with a Python MCP server (Dictator), worker legion scripts, and a Senate architecture brain.

## Architecture
- `src/` — C++ SKSE plugin: CommandDispatcher (singleton, jthread), JsonProcessor, CommandHooks (RE::Console, RE::Actor)
- `dictator/dictator.py` — Python MCP server (FastMCP, stdio transport)
- `dictator/rome_log.py` — Centralized JSON-line logger with 50MB auto-rotation (`logs/rome.jsonl`)
- `dictator/config.json` — Externalized path constants (root_dir, git_root, rome_root, etc.)
- `legions/legion_wrapper.py` — Subprocess harness: progress tracking, ROME signal parsing, usage extraction, manifest generation
- `legions/` — Worker scripts (centurion_64.py, zenith_orchestrator.py) and task artifact dirs
- `arsenal/core_arsenal.json` — Capability registry defining agent CLIs, args, and timeouts
- `senate/` — brain.py (soul spawner) + architects/T0-T63.md (sector manifestos)
- `tests/test_dictator.py` — pytest suite (18 tests covering tools, signals, usage parsing)

## Build
Cross-compiled via msvc-wine toolchain targeting Windows. CMake 3.20+, CommonLibSSE-NG, nlohmann/json.

## ROME Protocol Rules
1. All changes must be atomic and surgical — one concern per commit.
2. If a task exceeds 45s, sub-divide into smaller logical units.
3. Tasks are governed by manifestos in `legions/TASK_*/`.
4. Use ROME naming conventions: Imperial metaphors (Dictator, Legion, Senate, Centurion).

## Legion Execution Flow
1. `execute_legion()` loads capability from arsenal, creates task dir, sets `ROME_TASK_DIR` env
2. `legion_wrapper.py` runs the agent CLI as a subprocess with non-blocking I/O
3. Wrapper tracks progress (heartbeat lines → `progress.log` + in-memory list)
4. On completion: parses ROME signals, extracts usage from JSON output (Claude/Gemini), writes `manifest.json`
5. Dictator reads manifest for `progress` and `usage`, returns structured JSON to caller

## Usage Tracking
Agent CLIs (Claude, Gemini) are called with `--output-format json`. The wrapper's `parse_usage()` extracts:
- **Claude**: `input_tokens`, `output_tokens`, `cache_*_tokens`, `total_cost_usd`, model name
- **Gemini**: token counts from `stats.models.*.tokens`, model name
- **Others** (Codex, SAFE_SHELL): `usage: null` — graceful fallback

## MCP Server
The "asshole" MCP server runs via `dictator/dictator.py`. Tools are rooted at `/var/www/ftk_lms` for Drupal work, with `read_anywhere`/`write_anywhere` for absolute paths.
