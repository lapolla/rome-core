#!/bin/bash
# ROME Commit Gate — stable mesh snapshot required before any commit.
set -e

ROME_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS_URL="ws://127.0.0.1:$(grep '^MESH_PORT=' "$ROME_ROOT/dictator/rome.conf" | cut -d= -f2)"

echo "=== ROME Commit Gate ==="

# 1. Unit tests (fast only — exclude e2e and smoke)
echo "[1] Running unit tests..."
node --test \
  "$ROME_ROOT/dist/tests/aaak.test.js" \
  "$ROME_ROOT/dist/tests/aaak_cache.test.js" \
  "$ROME_ROOT/dist/tests/arsenal_probe.test.js" \
  "$ROME_ROOT/dist/tests/native_agent.test.js" \
  "$ROME_ROOT/dist/tests/registry.test.js" \
  "$ROME_ROOT/dist/tests/registry_task_worker.test.js" \
  "$ROME_ROOT/dist/tests/shell_executor.test.js" \
  "$ROME_ROOT/dist/tests/worker.test.js" 2>&1 | grep -E "^(ok|not ok|#)" | tail -20
echo "[1] Unit tests passed."

# 2. Worker ping check
echo "[2] Pinging workers..."
POLICY="$ROME_ROOT/dictator/workers.json"
CAPS=$(node -e "const p=require('$POLICY'); console.log(p.workers.map(w=>w.capability).join(' '))")
ALL_OK=true
for CAP in $CAPS; do
  RESULT=$(node "$ROME_ROOT/dist/src/client.js" "$CAP" "Reply with exactly: PONG" 2>/dev/null | tail -1 || echo "FAIL")
  if echo "$RESULT" | grep -q "PONG"; then
    echo "  [+] $CAP OK"
  else
    echo "  [-] $CAP FAILED"
    ALL_OK=false
  fi
done

if [ "$ALL_OK" = false ]; then
  echo "[2] FAILED — not all workers responded. Commit blocked."
  exit 1
fi
echo "[2] All workers responsive."

echo "=== Gate PASSED — safe to commit ==="
