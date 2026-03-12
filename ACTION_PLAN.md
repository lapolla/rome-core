# ROME Core — Action Plan (2026-03-12)

## Done Today
- [x] README.md: Removed stale Node.js references, updated MCP config to Python stdio
- [x] Nuked enforce_delegation.sh hook (was forcing write_anywhere over Edit)
- [x] legion_wrapper.py: Fixed progress log spam — "Awaiting thought..." now logs every ~5s instead of every 0.2s (96% reduction)

## Priority Tasks

### P0 — Quick Wins (S effort)
- [ ] **Fix tool/module count in docs** — README.md and CLAUDE.md say "47 tools across 10 modules", actual count is 51 tools across 12 modules (missing: tools_docs.py, tools_ws.py)
- [ ] **Systemd unit for daemon** — Create `ops/rome-dictator.service` so the daemon auto-restarts on failure. Currently dies silently with no supervisor.
- [ ] **Mark Claude cost tracking as N/A** — User is on Pro (flat-rate). Claude `cost_usd` in manifests is meaningless. Either null it out or add a config flag.

### P1 — Medium Effort
- [ ] **Task-scoped `rome_tail`** — Currently returns global log entries. Add `task_id` filter param so you can tail a specific task's logs without grepping manifests.
- [ ] **Verify WS auth enforcement** — `config.json` has a ws_token but confirm `ws_server.py` actually checks it on every connection.

### P2 — Larger Items (from TODO.md)
- [ ] **Agent WS Result Submission** — Give agents a small MCP tool `send_result(task_id, content)` that writes results via WS instead of file pipeline. Eliminates empty report bug entirely.
- [ ] **Dashboard: cost widget, retry button, campaign fan-out view**
- [ ] **Historical persistence** — Hydrate TaskRegistry from `logs/rome.jsonl` on startup so history survives daemon restarts.

## Not Doing
- Security "findings" about shell_exec/read_anywhere/write_anywhere — these are MCP tools called by the orchestrator, not a public API. Threat model doesn't apply.
- Externalizing hardcoded LLM pricing — not worth the complexity, prices change rarely, Claude costs are flat-rate anyway.
- Prefect MCP-level sandboxing — would require a custom proxy layer, too much effort for current use.