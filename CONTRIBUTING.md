# Contributing to ROME Core

## The Deletion Rule

Every PR that removes a symbol must, in the same PR, remove every reference to it — code, docs, memory, comments. CI enforces this for `CLAUDE.md` and `src/` via `scripts/check-doc-drift.sh` (run as `pretest`). If a refactor leaves you wanting to leave breadcrumbs, write a `CHANGELOG.md` entry instead.
