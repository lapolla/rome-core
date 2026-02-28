# ROME TODO

## Fixed
- [x] git tools (git_status, git_diff, git_commit, git_push) now accept `repo_path` param — no longer hardcoded to Drupal repo

## Fixed
- [x] Fallback chain extended: GEMINI→CODEX→OPENCODE with chained retry logic
- [x] Progress bars: richer keyword detection (reading/writing/compiling/testing/etc), step N/M parsing, percentage detection, error flagging
- [x] Senate brain.py integrated as `senate_brain` MCP tool in tools_stats.py (dispatches via GEMINI legion)
- [x] Centurion dashboard restored in execute_campaign — per-task aligned status lines + "Caesar's Consolidated Intelligence" summary
- [x] Prefect whitelist enforcement strengthened — explicit CRITICAL CONSTRAINT prompts + regex-based tool call audit (not just string matching)

- [x] Codex sandbox sync — auto-copies /tmp outputs and modified input_files back after CODEX runs (Phase 21)
- [x] Prefect enforcement hardened — pre-flight tool declaration + violations now mark task FAILED (not just warning)
- [x] Delegation heuristics — new `recommend_capability` MCP tool with keyword/volume scoring (GEMINI vs CODEX vs SAFE_SHELL)
- [x] ROME v3 Centurion hierarchy — CENTURION capability in arsenal, prompt patch, recommend_capability heuristics

## Fixed
- [x] Dictator MCP crash on startup — `callable | None` type hint (lowercase `callable` is a builtin function, not a type). Fixed in `core.py` and `tools_legion.py` by importing `Callable` from `collections.abc`.

## Open
- [ ] Agent-to-disk direct write — agents (GEMINI/Codex) should write files directly to disk instead of returning content through orchestrator context. Pattern: `gemini -p "produce file" > /path/file 2>/dev/null`. Needs: arsenal support for output redirection, or a `write_file` MCP tool agents can call. Biggest token waste source currently.
- [ ] Legion wrapper progress bars not visible in Claude Code terminal — `/dev/tty` writes go to underlying terminal, not Claude's UI. Progress bars work in standalone terminal and centurion dashboard but are invisible when dispatched from Claude Code. Need alternative rendering (e.g. write to a file Claude can tail, or use Claude's native task status).
- [ ] Prefect sandboxing is still prompt-level — true MCP-level tool filtering not possible with gemini CLI dispatch
- [x] Restore v1 Centurion dashboard — standalone centurion.py CLI with OrchestratorUI, launch_centurion MCP tool (fire-and-forget via /dev/tty), dynamic column alignment, JSON report written to file
- [ ] Token discipline enforcement — if Claude (Dictator) consumes more than ~500 tokens on any single task (reading files, analyzing code, writing edits), it must be whipped down. ALL work beyond trivial orchestration commands MUST be delegated to slaves (GEMINI/CODEX/SAFE_SHELL). Claude is the emperor — it commands, it does not labor. Violations = wasted budget.
