# ROME Core — Backlog

Real fixes deferred out of the v7 cleanup effort. Each one deserves its own
PR; the freeze rule applies (commit-discipline ratio: 4 of every 5 commits
\`chore\`/\`fix\`/\`docs\`/\`test\`, only 1 in 5 may be \`feat\`).

## Out of scope by user decision
- **WS auth / 127.0.0.1 bind** — explicitly excluded.

## Real bugs, separate PRs
- **\`cancel\` / \`interrupt\` WS commands** — currently undocumented and unimplemented; either implement or stay-removed (see CLAUDE.md "Removed in v7" note).
- **\`MeshReducer\` → \`Blackboard\` wiring** — the reducer reduces tasks but doesn't surface state through the Blackboard.
- **Project-totals single source of truth** — \`projectTotalCost\` / \`projectTotalTokens\` are accumulated in two places (the JSONL replay path and the live submit path) and can double-count.
- **Periodic tick** — \`scheduleTick\` is called on dispatch but there is no idle-time tick to clean up zombies / refresh probes.
- **Honor \`arsenal.timeout\`** — capability config has a \`timeout\` field, but worker invocations don't enforce it.
