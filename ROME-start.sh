#!/bin/bash
# ROME: START PEER MESH
ROME_ROOT="$(cd "$(dirname "$0")" && pwd)"
WS_URL="ws://127.0.0.1:8741"
WS_TOKEN="ROME_V4_SECURE_TOKEN"

# 0. Kill stale workers and daemon
pkill -f "peer_server.js" 2>/dev/null || true
pkill -f "legion_worker.js" 2>/dev/null || true
sleep 1

# 1. Start Peer Server (Daemon)
echo "Starting ROME Peer Server (Port 8741)..."
nohup node "$ROME_ROOT/dist/src/peer_server.js" DAEMON 8741 > "/tmp/rome-daemon.log" 2>&1 &
sleep 2

# 2. Start Workers
start_worker() {
    local cap=$1
    shift
    echo "Starting worker: $cap"
    nohup node "$ROME_ROOT/dist/src/legion_worker.js" \
        --mode worker \
        --capabilities "$cap" \
        --ws-url "$WS_URL" \
        --ws-token "$WS_TOKEN" \
        -- "$@" > "/tmp/rome-worker-$cap.log" 2>&1 &
}

# GEMINI
GEMINI_CLI="$HOME/projects/gemini-cli/bundle/gemini.js"
start_worker "GEMINI" node "$GEMINI_CLI" --sandbox false --include-directories "$ROME_ROOT" --yolo --output-format json -m gemini-3.1-pro-preview -p

# SAFE_SHELL
start_worker "SAFE_SHELL" bash -c

# TEST
start_worker "TEST" npm test --prefix "$ROME_ROOT"

# MISTRAL (Upgraded with Native WS)
start_worker "MISTRAL" python3 -m vibe.cli.entrypoint "env:PYTHONPATH=/home/paul-kane/projects/mistral-cli" --agent auto-approve --output text -p

# CLAUDE
start_worker "CLAUDE" claude --dangerously-skip-permissions --output-format json -p

# GEMMA (Ollama)
start_worker "GEMMA" env ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 claude --dangerously-skip-permissions --output-format json --model gemma4:e4b -p

# ... 
ROME_VERSION=$(grep '"version":' "$ROME_ROOT/package.json" | cut -d'"' -f4)
echo "ROME v$ROME_VERSION Mesh restarted."
