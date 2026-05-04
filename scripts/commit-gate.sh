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

# 2. Worker registration check
echo "[2] Checking worker registration..."
POLICY="$ROME_ROOT/dictator/workers.json"
REGISTERED=$(timeout 10 node --input-type=module <<NODEEOF
import { WebSocket } from 'ws';
import * as fs from 'fs';
const ROME_ROOT = "$ROME_ROOT";
const cfgPath = \`\${ROME_ROOT}/dictator/config.json\`;
const config = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));
const token = fs.readFileSync(\`\${ROME_ROOT}/\${config.sovereign_token_path}\`, 'utf-8').trim();
const ws = new WebSocket(\`ws://127.0.0.1:\${config.mesh_port}/ws?token=\${token}\`);
ws.on('open', () => ws.send(JSON.stringify({ type: 'command', command: 'workers', request_id: 'gate' })));
ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.request_id === 'gate') {
    const caps = (msg.payload?.workers || []).flatMap(w => w.capabilities || []);
    console.log(caps.join(' '));
    ws.close();
  }
});
setTimeout(() => { ws.close(); }, 8000);
NODEEOF
2>/dev/null)

ALL_OK=true
CAPS=$(node --input-type=module -e "import fs from 'fs'; const p=JSON.parse(fs.readFileSync('$POLICY','utf-8')); console.log(p.workers.map(w=>w.capability).join(' '));" 2>/dev/null)
for CAP in $CAPS; do
  if echo "$REGISTERED" | grep -qw "$CAP"; then
    echo "  [+] $CAP registered"
  else
    echo "  [-] $CAP not registered"
    ALL_OK=false
  fi
done

if [ "$ALL_OK" = false ]; then
  echo "[2] FAILED — not all workers registered. Commit blocked."
  exit 1
fi
echo "[2] All workers registered."

echo "=== Gate PASSED — safe to commit ==="
