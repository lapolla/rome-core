# ROME TODO

## Open Bugs

- [ ] **GEMINI empty report bug** — report file occasionally overwritten with previous task's OK string. `output_path` fallback mitigates but doesn't fully fix the root cause (GEMINI CLI cannot write directly to arbitrary paths).
- [x] **Ghost tasks on daemon restart** — `sweep_orphans()` in TaskRegistry + Starlette lifespan in daemon.py marks all registered/running tasks as failed on startup.
- [ ] **`rome_tail` not task-scoped** — returns global log entries, not filtered by task_id. Hard to confirm task results without polling the manifest directly.

## Open Infrastructure

- [ ] **No daemon supervisor** — daemon dies on bad signals with no restart. Add systemd unit or supervisord config (`ops/rome-dictator.service`).
- [ ] **MCP server cleanup** — "asshole" Node server has too many tools. Should be stripped to lean ROME-only tools; non-ROME tools (Drupal, Skyrim) can move to domain-specific servers.
- [ ] **Prefect sandboxing is prompt-level only** — true MCP-level tool filtering not possible with gemini CLI dispatch. Would require a custom MCP proxy layer.

## Dashboard Features

- [ ] **Cost widget** — show cumulative session cost on dashboard. `rome_costs` data exists; needs a `cost_update` event listener + display widget.
- [ ] **Failed task retry button** — "Retry" button on FAILED cards sends WS `dispatch` command to re-run.
- [ ] **Campaign fan-out view** — group child tasks under parent campaign; show aggregate campaign progress.
- [ ] **Task output viewer** — click task card to view report file contents inline via WS `read_report` command.
- [ ] **Historical persistence** — hydrate TaskRegistry from `logs/rome.jsonl` on startup so history survives restarts.
- [ ] **Filter/search** — filter task cards by status, capability, date.

## Backlog (Larger Items)

- [ ] **Headless orchestrator mode (dashboard)** — external client (Haiku/Flash) orchestrates via WS `dispatch` command from the dashboard UI. The "make the throne cheap" endgame; `client/orchestrator.py` CLI exists but dashboard integration is missing.
- [ ] **Agent WS Result Submission** — give Gemini/agents a small MCP server with `send_result(task_id, content)` tool. Agent calls `send_result` instead of writing to stdout/file. Eliminates report file pipeline + empty report bug entirely.
  - Result flow: agent → MCP tool → ws_client → daemon → dashboard
  - Add to arsenal: `--allowed-mcp-server-names rome-results`
- [ ] **Gemini CLI WS Daemon Mode** — fork gemini-cli (Apache 2.0), add `--ws-daemon` mode: persistent worker that connects to `ws://127.0.0.1:8741/ws`, receives task payloads, sends results back via WS. Eliminates subprocess-per-task model entirely.
