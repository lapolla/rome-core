# ROME: Remote Orchestrated Model Execution

A Python MCP orchestration framework. Provides a persistent daemon that dispatches AI workers (Legions) in parallel, streams live progress via WebSocket, and serves a browser dashboard.

## Imperial Hierarchy

```
Emperor (You)
  └── Dictator (any LLM — Claude, GPT, Gemini)
        └── Centurion (optional nested orchestrator)
              └── Legions (GEMINI | CODEX | SAFE_SHELL | OPENCODE)
```

## Architecture

```
dictator/
  daemon.py          ASGI app — mounts MCP SSE + WS + dashboard (port 8741)
  dictator.py        Stdio entry point (legacy / transition)
  core.py            Config, run_cmd/run_cmd_stream, EventBus, mcp instance
  ws_server.py       WS protocol handler (dispatch, cancel, status, reset, ping)
  ws_client.py       Internal WS sender used by MCP tools (fire-and-forget + sync)
  events.py          RomeEvent dataclass + pub/sub EventBus
  tools_*.py         MCP tool modules (fs, git, drupal, legion, skyrim, desktop, media, gc, stats, prefect)
  config.json        Path constants (17 keys)
  legion_patches.json  Capability-specific prompt injections
legions/
  legion_wrapper.py  Subprocess harness for LLM workers — parses ROME signals + usage + manifests
  shell_executor.py  Dedicated bash executor for SAFE_SHELL (no JSON, no LLM dance)
  centurion_wrapper.py  Campaign orchestrator with retry loop + dashboard
  dashboard.py       Inline ANSI TUI for campaign progress
  .cache/            1-hour TTL result cache
arsenal/
  core_arsenal.json  Capability registry (CLIs, args, timeouts)
senate/
  brain.py           Sector manifesto dispatcher
  architects/        64 sector manifestos (T0.md–T63.md)
client/
  orchestrator.py    Headless CLI orchestrator (Haiku/Flash → WS dispatch)
```

## Quick Start

### Start the daemon

```bash
python3 dictator/daemon.py
# MCP-over-SSE:  http://localhost:8741/mcp
# WebSocket:     ws://localhost:8741/ws
# Dashboard:     http://localhost:8741/dashboard/
```

### Claude Code (MCP over SSE)

In `~/.claude/mcp-servers.json`:
```json
{
  "mcpServers": {
    "asshole": {
      "command": "node",
      "args": ["/home/paul-kane/projects/mcp-server/server.mjs"]
    }
  }
}
```

### Headless orchestrator (no Claude Code required)

```bash
echo "Fix the bug in main.py and run tests" | python3 client/orchestrator.py -
```

Haiku (~$0.0002) breaks the task into subtasks and dispatches them to the daemon via WS. Workers (GEMINI/CODEX/SAFE_SHELL) do the actual work. Output is JSONL event stream on stdout.

**Cost comparison (10 tasks):**
- Headless: ~$0.002 (orchestrator) + ~$0.05 (workers) = ~$0.052
- Claude Code: ~$0.15 (Opus idle) + ~$0.05 (workers) = ~$0.20

## MCP Tools (47 across 10 modules)

| Module | Tools |
|--------|-------|
| `tools_fs` | shell_exec, fs_read, fs_write, list_directory, read_anywhere, write_anywhere |
| `tools_git` | git_status, git_diff, git_commit, git_push |
| `tools_drupal` | rsync_ftk_modules, drush_run, drupal_fj_run |
| `tools_legion` | execute_legion, execute_campaign, rome_dispatch, recommend_capability, launch_centurion |
| `tools_skyrim` | skyrim_console, skyrim_read_state, skyrim_face_actor, skyrim_follow_actor, skyrim_pivot, skyrim_compound_move, compile_papyrus |
| `tools_desktop` | desktop_screenshot, desktop_click, desktop_type_text, desktop_press_key, desktop_find_window, desktop_focus_window, desktop_get_mouse_location, desktop_notify |
| `tools_media` | music_play, music_stop, music_status, http_fetch, fetch_mo2_mod |
| `tools_gc` | gc_legions, legion_stats |
| `tools_stats` | rome_tail, rome_costs, rome_health, rome_find, senate_query, senate_brain |
| `tools_prefect` | execute_prefect |

## Key Features

### Capabilities & Failover

| Capability | Role | Fallback |
|------------|------|---------|
| GEMINI | High-speed generalist coding/analysis | → CODEX → OPENCODE |
| CODEX | Code manipulation, repo insight | → GEMINI |
| SAFE_SHELL | Direct bash (shell_executor.py, no LLM) | retry once |
| OPENCODE | Local/OSS models | — |
| CENTURION | Nested orchestrator dispatching sub-legions | — |

### Campaign System

`execute_campaign` runs parallel tasks with DAG dependency management. Failed tasks retry up to 3x through the fallback chain. Results cached for 1 hour in `legions/.cache`.

### WebSocket Protocol

Server listens at `ws://localhost:8741/ws`. Auth via `Authorization: Bearer <token>` header or `?token=` query param.

Commands (client → server):
```json
{"type": "dispatch", "payload": {"task_id": "...", "capability": "GEMINI", "prompt": "..."}}
{"type": "status",   "payload": {"task_id": "..."}}
{"type": "cancel",   "payload": {"task_id": "..."}}
{"type": "reset",    "payload": {}}
{"type": "ping"}
```

Events (server → client):
```json
{"type": "dispatch_start", "task_id": "...", "capability": "..."}
{"type": "progress",       "task_id": "...", "percent": 50, "message": "..."}
{"type": "complete",       "task_id": "...", "status": "SUCCESS", "report": "/path/..."}
{"type": "error",          "task_id": "...", "message": "..."}
{"type": "heartbeat"}
```

### Senate

64 sector manifestos (`senate/architects/T0.md`–`T63.md`). `senate_brain` MCP tool dispatches a GEMINI legion with the relevant manifesto as context. `senate_query` finds which sector handles a given concern.

### Prefect Agents

`execute_prefect` provides domain-scoped autonomous agents: `drupal`, `skyrim`, `git`, `investigate`, `full`. Tool use is audited post-run against each domain's whitelist.

## ROME Signal Protocol

LLM workers use these tags to communicate with `legion_wrapper.py`:

```
[ROME_START] ... [ROME_END]     Primary artifact
[ROME_META: key=value]          Inject into manifest.json
[ROME_STATUS: SUCCESS|FAILED|RETRY]   Explicit outcome
```

Every task produces a `manifest.json`:
```json
{
  "rome_v": "2.0",
  "task_id": "...",
  "status": "SUCCESS",
  "usage": {"model": "...", "input_tokens": 3486, "output_tokens": 27, "cost_usd": null},
  "progress": ["0% ...", "50% ...", "100% ..."],
  "artifacts": [{"path": "report_TASK_ID.txt", "type": "extracted"}],
  "runtime": {"elapsed_s": 12.5, "exit_code": 0}
}
```

## Environment

- OS: Linux (Ubuntu 22.04+)
- Python 3.10+
- Node.js v18+ (legacy MCP server)
- Workspace: `/home/paul-kane/projects/rome-core`
- Temp: `/home/paul-kane/tmp`
- Daemon port: 8741
