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

## Open
- [ ] Prefect sandboxing is still prompt-level — true MCP-level tool filtering not possible with gemini CLI dispatch
- [x] Restore v1 Centurion dashboard — standalone centurion.py CLI with OrchestratorUI, launch_centurion MCP tool (fire-and-forget via /dev/tty), dynamic column alignment, JSON report written to file
