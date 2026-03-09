# ROME v3 — Centurion Hierarchy Implementation Plan

## Hierarchy
Emperor (User) → Dictator (any LLM) → Centurion (any LLM) → Legionnaires (any LLM)

## Phase 1: Arsenal + Prompt Patch
- Add CENTURION capability to arsenal/core_arsenal.json (same CLI as GEMINI but longer timeout)
- Add centurion prompt patch to dictator/legion_patches.json:
  "You are a Centurion. For simple tasks (grep, file reads, small edits), delegate to Legionnaires:
   - codex exec --full-auto --skip-git-repo-check 'task description'
   - opencode run 'task description'
   Only do complex analysis yourself. Aggregate all sub-worker results into your report."

## Phase 2: Recommend + Dispatch
- Update recommend_capability to suggest CENTURION for complex multi-step tasks
- execute_legion applies centurion prompt patch when capability=CENTURION

## Phase 3: Docs
- Update CLAUDE.md, README.md, TODO.md with new hierarchy
- Update playbook.md with CENTURION dispatch pattern

## Files to change:
1. arsenal/core_arsenal.json — add CENTURION entry
2. dictator/legion_patches.json — add CENTURION prompt patch
3. dictator/tools_legion.py — update recommend_capability heuristics
4. CLAUDE.md, README.md, TODO.md — docs
