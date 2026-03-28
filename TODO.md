# ROME TODO

## Open Bugs

- [x] **GEMINI empty report bug** — Fixed by `rome-results` MCP tool + WebSocket `submit_result` pipeline.
- [x] **Ghost tasks on daemon restart** — `sweep_orphans()` in TaskRegistry marks old tasks as failed on startup.
- [x] **`rome_tail` not task-scoped** — Fixed via `grep` optimization.

## Open Infrastructure

- [x] **No daemon supervisor** — Fixed. `ops/rome-dictator.service` installed and enabled.
- [ ] **MCP server cleanup** — "asshole" Node server has too many tools. Should be stripped to lean ROME-only tools.
- [ ] **Prefect sandboxing is prompt-level only** — true MCP-level tool filtering not possible with current dispatch.

## Dashboard Features

- [x] **Cost widget** — Added Session Cost display.
- [x] **Campaign fan-out view** — Added hierarchical grouping via `parent_task_id`.
- [x] **Task output viewer** — click task card to view report file contents inline via WS `read_report` command.
- [x] **Historical persistence** — Implemented `hydrate_from_log()` in TaskRegistry.
- [ ] **Filter/search** — filter task cards by status, capability, date.

## Backlog (Larger Items)

- [ ] **Headless orchestrator mode (dashboard)** — external client (Haiku/Flash) orchestrates via WS `dispatch` command.
- [x] **Agent WS Result Submission** — Implemented via `rome-results` MCP server.
- [ ] **Gemini CLI WS Daemon Mode** — fork gemini-cli, add `--ws-daemon` mode for persistent workers.
