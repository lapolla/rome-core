#!/bin/bash
# ROME doc/code drift guard.
# Fails if CLAUDE.md mentions src paths that don't exist, if its WS command
# table diverges from peer_server.ts, or if stale FIX-N markers reappear.
# Phase 4.1 + 4.3 of v7 cleanup.

set -u

ROME_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROME_ROOT"

FAIL=0

echo "[drift] src paths in CLAUDE.md"
PATHS=$(grep -oE '`src/[a-zA-Z0-9_/-]+\.ts`' CLAUDE.md | tr -d '`' | sort -u)
for p in $PATHS; do
  if [ ! -e "$p" ]; then
    echo "  MISSING: $p"
    FAIL=1
  fi
done
[ $FAIL -eq 0 ] && echo "  ok"

echo "[drift] WS command table vs peer_server.ts"
DOC_CMDS=$(grep -oE '^\| `[a-z_]+`' CLAUDE.md | sed 's/| `//; s/`$//' | sort -u)
CODE_CMDS=$(grep -oE "case '[a-z_]+'" src/peer_server.ts \
  | sed "s/case '//; s/'$//" \
  | grep -vE '^(progress|complete|error)$' \
  | sort -u)

DOC_ONLY=$(comm -23 <(echo "$DOC_CMDS") <(echo "$CODE_CMDS"))
CODE_ONLY=$(comm -13 <(echo "$DOC_CMDS") <(echo "$CODE_CMDS"))
if [ -n "$DOC_ONLY" ]; then
  echo "  in CLAUDE.md but not in peer_server.ts:"
  echo "$DOC_ONLY" | sed 's/^/    /'
  FAIL=1
fi
if [ -n "$CODE_ONLY" ]; then
  echo "  in peer_server.ts but not in CLAUDE.md:"
  echo "$CODE_ONLY" | sed 's/^/    /'
  FAIL=1
fi
[ -z "$DOC_ONLY" ] && [ -z "$CODE_ONLY" ] && echo "  ok"

echo "[drift] FIX-N comment lint"
FIX_HITS=$(grep -rEn '// FIX [0-9]' src/ 2>/dev/null || true)
if [ -n "$FIX_HITS" ]; then
  echo "  stale FIX markers:"
  echo "$FIX_HITS" | sed 's/^/    /'
  FAIL=1
else
  echo "  ok"
fi

TODO_HITS=$(grep -rEn '// (TODO|XXX)\b' src/ 2>/dev/null || true)
if [ -n "$TODO_HITS" ]; then
  TODO_COUNT=$(echo "$TODO_HITS" | wc -l)
  echo "[drift] warning: $TODO_COUNT TODO/XXX comment(s) in src/"
fi

if [ $FAIL -ne 0 ]; then
  echo "[drift] FAILED"
  exit 1
fi
echo "[drift] passed"
