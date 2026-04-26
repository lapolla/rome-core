#!/bin/bash
# ROME: START PEER MESH

export ROME_ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="$ROME_ROOT/dictator/rome.conf"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: rome.conf not found at $CONFIG_PATH"
    exit 1
fi

MESH_PORT=$(grep '^MESH_PORT=' "$CONFIG_PATH" | cut -d= -f2)
WS_URL="ws://127.0.0.1:$MESH_PORT"

# 0. Kill stale workers and daemon
pkill -f "peer_server.js" 2>/dev/null || true
pkill -f "legion_worker.js" 2>/dev/null || true
pkill -f "vibe.cli.entrypoint" 2>/dev/null || true
pkill -f "native_agent.js" 2>/dev/null || true
sleep 1

# 1. Start Peer Server (Daemon)
echo "Starting ROME Peer Server (Port $MESH_PORT)..."
nohup env XDG_RUNTIME_DIR="/run/user/$(id -u)" \
          DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
          PULSE_SERVER="/run/user/$(id -u)/pulse/native" \
          node "$ROME_ROOT/dist/src/peer_server.js" DAEMON "$MESH_PORT" > "/tmp/rome-daemon.log" 2>&1 &
sleep 2

# 2. Start Workers
# `start_worker_if` gates the spawn on availability. First arg is a test command
# whose exit code decides whether to spawn. Missing binaries / unreachable
# backends no longer produce doomed workers with silent stderr.
start_worker() {
    local cap=$1
    shift
    echo "Starting worker: $cap"
    local args=(
        "--mode" "worker"
        "--capabilities" "$cap"
        "--ws-url" "$WS_URL"
        "--"
        "$@"
    )
    nohup node "$ROME_ROOT/dist/src/legion_worker.js" "${args[@]}" > "/tmp/rome-worker-$cap.log" 2>&1 &
}

start_worker_if() {
    local cap=$1
    local probe=$2
    shift 2
    if eval "$probe" >/dev/null 2>&1; then
        start_worker "$cap" "$@"
    else
        echo "Skipping $cap: probe failed ($probe)"
    fi
}

# GEMINI — requires gemini-cli bundle
GEMINI_CLI="$HOME/projects/gemini-cli/bundle/gemini.js"
start_worker_if "GEMINI" "test -f '$GEMINI_CLI'" \
    node "$GEMINI_CLI" --sandbox false --include-directories "$ROME_ROOT" --yolo --output-format json -m '{MODEL}' -p

# MISTRAL — requires mistral-cli python module
start_worker_if "MISTRAL" "test -d /home/paul-kane/projects/mistral-cli && command -v python3" \
    env PYTHONPATH=/home/paul-kane/projects/mistral-cli python3 -m vibe.cli.entrypoint --agent auto-approve --output text --max-turns 1 -p

# CLAUDE — requires claude CLI on PATH
start_worker_if "CLAUDE" "command -v claude" \
    claude --dangerously-skip-permissions --output-format json -p

# GEMMA — JS-Native agent via Ollama
if curl -sf --max-time 1 http://localhost:11434/ >/dev/null 2>&1; then
    echo "Starting native worker: GEMMA"
    nohup node "$ROME_ROOT/dist/src/native_agent.js" --capability GEMMA --model gemma4:e4b --ws-url "$WS_URL/ws" > "/tmp/rome-worker-GEMMA.log" 2>&1 &
else
    echo "Skipping GEMMA: Ollama unreachable"
fi

# ... 
ROME_VERSION=$(grep '"version":' "$ROME_ROOT/package.json" | cut -d'"' -f4)
echo "ROME v$ROME_VERSION Mesh restarted."
