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
- [x] Agent-to-disk direct write — `rome_dispatch(output_path=...)` tells agent to write directly. Codex sandbox fixed (`--dangerously-bypass-approvals-and-sandbox`). Zero content through orchestrator.
- [x] Legion wrapper progress bars in Claude Code — centurion.py non-TTY mode prints clean stdout lines, run via Bash tool for live streaming. progress.log polling + time-based ramp for visual progress.
- [ ] Prefect sandboxing is still prompt-level — true MCP-level tool filtering not possible with gemini CLI dispatch
- [x] Restore v1 Centurion dashboard — standalone centurion.py CLI with OrchestratorUI, launch_centurion MCP tool (fire-and-forget via /dev/tty), dynamic column alignment, JSON report written to file
- [x] Quiet MCP returns — tools return minimal OK/ERR. rome_dispatch, shell_exec, git tools, write_anywhere all slimmed down.
- [x] Empty report bug — rome_dispatch was overwriting wrapper's report file with "OK:task_id". Fixed: check if report exists before writing.
- [x] WebSocket transport — daemon.py with Starlette/Uvicorn, EventBus, TaskRegistry, WS server, live dashboard at :8741/dashboard/.
- [x] Fire-and-forget dispatch — `rome_dispatch(fire_and_forget=True)` prevents MCP timeout drops on long tasks.
- [x] Output path fallback — `rome_dispatch(output_path=...)` copies report to output_path when agent cannot write directly.
- [ ] Token discipline enforcement — if Claude (Dictator) consumes more than ~500 tokens on any single task (reading files, analyzing code, writing edits), it must be whipped down. ALL work beyond trivial orchestration commands MUST be delegated to slaves (GEMINI/CODEX/SAFE_SHELL). Claude is the emperor — it commands, it does not labor. Violations = wasted budget.
