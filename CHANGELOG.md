
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
