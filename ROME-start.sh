#!/bin/bash
# ROME: START PEER MESH

ROME_ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="$ROME_ROOT/dictator/rome.conf"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: rome.conf not found at $CONFIG_PATH"
    exit 1
fi

MESH_PORT=$(grep '^MESH_PORT=' "$CONFIG_PATH" | cut -d= -f2)
TOKEN_REL_PATH=$(grep '^SOVEREIGN_TOKEN_PATH=' "$CONFIG_PATH" | cut -d= -f2)

TOKEN_PATH="$ROME_ROOT/$TOKEN_REL_PATH"
WS_TOKEN=$(cat "$TOKEN_PATH")
WS_URL="ws://127.0.0.1:$MESH_PORT"

# 0. Kill stale workers and daemon
pkill -f "peer_server.js" 2>/dev/null || true
pkill -f "legion_worker.js" 2>/dev/null || true
sleep 1

# 1. Start Peer Server (Daemon)
echo "Starting ROME Peer Server (Port $MESH_PORT)..."
nohup node "$ROME_ROOT/dist/src/peer_server.js" DAEMON "$MESH_PORT" > "/tmp/rome-daemon.log" 2>&1 &
sleep 2

# 2. Start Workers
start_worker() {
    local cap=$1
    shift
    echo "Starting worker: $cap"
    # We use an array to preserve arguments exactly
    local args=(
        "--mode" "worker"
        "--capabilities" "$cap"
        "--ws-url" "$WS_URL"
        "--ws-token" "$WS_TOKEN"
        "--"
        "$@"
    )
    nohup node "$ROME_ROOT/dist/src/legion_worker.js" "${args[@]}" > "/tmp/rome-worker-$cap.log" 2>&1 &
}

# GEMINI
GEMINI_CLI="$HOME/projects/gemini-cli/bundle/gemini.js"
start_worker "GEMINI" node "$GEMINI_CLI" --sandbox false --include-directories "$ROME_ROOT" --yolo --output-format json -m gemini-3.1-pro-preview -p

# SAFE_SHELL (Scaled to 11 for parallel decomposition)
for i in {1..11}; do
    start_worker "SAFE_SHELL" bash -c
done

# MISTRAL (Upgraded with Native WS)
start_worker "MISTRAL" env PYTHONPATH=/home/paul-kane/projects/mistral-cli python3 -m vibe.cli.entrypoint --agent auto-approve --output text -p

# CLAUDE
start_worker "CLAUDE" claude --dangerously-skip-permissions --output-format json -p

# GEMMA (Ollama)
start_worker "GEMMA" env ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 claude --dangerously-skip-permissions --output-format json --model gemma4:e4b -p

# ... 
ROME_VERSION=$(grep '"version":' "$ROME_ROOT/package.json" | cut -d'"' -f4)
echo "ROME v$ROME_VERSION Mesh restarted."
