# Project Status
*Last Updated: 2026-03-09 20:21:07*

## Features
- **Pure WebSocket control plane** [completed]: Eliminated all HTTP API routes (/api/event, /api/reset, /api/clear, /api/status). All daemon communication now goes through WS. New ws_client.py provides persistent fire-and-forget sender + sync command client for MCP tools.
- **Process group isolation** [completed]: Added start_new_session=True to all subprocess spawns in core.py (run_cmd, run_cmd_stream) and legion_wrapper.py. Gemini/Node.js no longer kills the Python MCP server via signal propagation.
- **Stderr pipe deadlock fix** [completed]: Removed sys.stderr.buffer.write() from run_cmd_stream. Progress lines no longer block the MCP server's stdio pipe during long Gemini runs.
- **reset_tasks MCP tool** [completed]: New tool that clears all tasks (including REGISTERED zombies) from the daemon registry via WS reset command. Hooked into auto_gc() so it fires on every MCP server startup.
- **Dashboard RUNNING counter fix** [completed]: Fixed REGISTERED tasks being counted as RUNNING in dashboard stats. RUNNING now only counts tasks in actual running state.
- **Dashboard pure WS** [completed]: Replaced HTTP fetch polling of /api/status with WS status summary command. DAEMON chip shows live status. Uptime now sourced from WS response.
- **Headless orchestrator upgraded** [completed]: Upgraded from claude-3-haiku-20240307 to claude-sonnet-4-6 for better routing quality.
- **TaskRegistry.clear_all()** [completed]: Added clear_all() method to TaskRegistry to complement clear_finished(). Removes all tasks regardless of status.
- **WS protocol expanded** [completed]: Added reset, clear, event, and status(summary) commands to ws_server.py _handle_command dispatcher.

## Verification Checklist
- [ ] Daemon starts clean with no HTTP routes — /api/* returns 404
- [ ] Dashboard DAEMON chip shows OK via WS, no fetch() calls
- [ ] MCP reconnect triggers auto_gc which resets zombie tasks via WS
- [ ] Gemini runs no longer kill MCP server (start_new_session=True)
- [ ] reset_tasks MCP tool clears all tasks including REGISTERED
- [ ] RUNNING counter in dashboard excludes REGISTERED tasks
- [ ] Headless orchestrator uses claude-sonnet-4-6
