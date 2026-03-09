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
