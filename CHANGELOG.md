## Update: 2026-03-09

### Fixes
- **rome_dispatch output_path fallback**: Copies report file to output_path when agent CLI cannot write directly (GEMINI). Previously returned ERR even on successful tasks.
- **rome_dispatch fire_and_forget**: New `fire_and_forget=True` param starts task in background asyncio.Task, returns `DISPATCHED:{task_id}` immediately. Prevents MCP connection drops caused by long-running legion tasks blocking the stdio pipe.

### Docs
- DASHBOARD_TODO.md: Feature roadmap for ROME Dashboard (9 items, prioritized HIGH/MEDIUM/LOW)
- TODO.md: Marked WebSocket transport as complete
- CLAUDE.md: Documented fire_and_forget and output_path fallback


## Update: 2026-02-28 19:08:31

### Features Updated
- **Token Discipline Guard** (complete): MAX_OUTPUT_CHARS=2000 truncation in _execute_legion_impl, writes full output to report file, returns path reference
- **Progress Trimming** (complete): Progress arrays trimmed to first 3 + last 3 entries, 95%+ reduction in MCP response bloat
- **Cache Fixes** (complete): rome_dispatch now passes no_cache param, new clear_cache MCP tool
- **Token Accounting** (complete): Estimated outbound tokens logged at all 3 MCP return points (execute_legion, execute_campaign, rome_dispatch)
- **MEMORY.md Routing Table** (complete): Mandatory slave routing decision table added at top of MEMORY.md

### Verification
- [x] Progress trimming verified: 365 lines -> 7 lines in MCP response
- [x] clear_cache tool: wiped 28 stale entries
- [x] no_cache on rome_dispatch: fresh execution confirmed
- [x] Token accounting: token_guard entries in rome.jsonl
- [x] Syntax check passed on tools_legion.py

## Update: 2026-02-28 22:37:05

### Features Updated
- **ROME Silent Protocol** (complete): Added ROME_SILENT env var support to suppress progress bars in the prompt.
- **Real-time UI Alignment** (complete): Redirected progress bars to stderr and optimized streaming for carriage returns.
- **Chunk-based Command Streaming** (complete): Replaced line-buffering with granular reads to support in-place UI updates.
- **High-Fidelity Visuals** (complete): Restored solid Unicode blocks (█) and ANSI colors to the Legionnaire UI.

### Verification
- [x] Verified live progress rendering in shell_exec results
- [x] Confirmed ROME_SILENT effectively disables visual overrides
- [x] Validated chunk-based streaming with high-concurrency campaigns

## Update: 2026-03-09 20:21:07

### Features Updated
- **Pure WebSocket control plane** (completed): Eliminated all HTTP API routes (/api/event, /api/reset, /api/clear, /api/status). All daemon communication now goes through WS. New ws_client.py provides persistent fire-and-forget sender + sync command client for MCP tools.
- **Process group isolation** (completed): Added start_new_session=True to all subprocess spawns in core.py (run_cmd, run_cmd_stream) and legion_wrapper.py. Gemini/Node.js no longer kills the Python MCP server via signal propagation.
- **Stderr pipe deadlock fix** (completed): Removed sys.stderr.buffer.write() from run_cmd_stream. Progress lines no longer block the MCP server's stdio pipe during long Gemini runs.
- **reset_tasks MCP tool** (completed): New tool that clears all tasks (including REGISTERED zombies) from the daemon registry via WS reset command. Hooked into auto_gc() so it fires on every MCP server startup.
- **Dashboard RUNNING counter fix** (completed): Fixed REGISTERED tasks being counted as RUNNING in dashboard stats. RUNNING now only counts tasks in actual running state.
- **Dashboard pure WS** (completed): Replaced HTTP fetch polling of /api/status with WS status summary command. DAEMON chip shows live status. Uptime now sourced from WS response.
- **Headless orchestrator upgraded** (completed): Upgraded from claude-3-haiku-20240307 to claude-sonnet-4-6 for better routing quality.
- **TaskRegistry.clear_all()** (completed): Added clear_all() method to TaskRegistry to complement clear_finished(). Removes all tasks regardless of status.
- **WS protocol expanded** (completed): Added reset, clear, event, and status(summary) commands to ws_server.py _handle_command dispatcher.

### Verification
- [x] Daemon starts clean with no HTTP routes — /api/* returns 404
- [x] Dashboard DAEMON chip shows OK via WS, no fetch() calls
- [x] MCP reconnect triggers auto_gc which resets zombie tasks via WS
- [x] Gemini runs no longer kill MCP server (start_new_session=True)
- [x] reset_tasks MCP tool clears all tasks including REGISTERED
- [x] RUNNING counter in dashboard excludes REGISTERED tasks
- [x] Headless orchestrator uses claude-sonnet-4-6
