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

# Wait for processes to actually die (up to 5s), then force-kill
for pat in "peer_server.js" "legion_worker.js" "vibe.cli.entrypoint" "native_agent.js"; do
    for i in $(seq 1 5); do
        pgrep -f "$pat" >/dev/null 2>&1 || break
        sleep 1
    done
    pkill -9 -f "$pat" 2>/dev/null || true
done

export GEMINI_CLI="$HOME/projects/gemini-cli/bundle/gemini.js"
# 1. Start Peer Server (Daemon)
echo "Starting ROME Peer Server (Port $MESH_PORT)..."
nohup env XDG_RUNTIME_DIR="/run/user/$(id -u)" \
          DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
          PULSE_SERVER="/run/user/$(id -u)/pulse/native" \
          node "$ROME_ROOT/dist/src/peer_server.js" DAEMON "$MESH_PORT" > "/tmp/rome-daemon.log" 2>&1 &

# Wait for daemon to be listening (up to 10s)
for i in $(seq 1 10); do
    nc -z 127.0.0.1 "$MESH_PORT" 2>/dev/null && break
    sleep 1
done
if ! nc -z 127.0.0.1 "$MESH_PORT" 2>/dev/null; then
    echo "Error: Daemon failed to start on port $MESH_PORT. Check /tmp/rome-daemon.log"
    exit 1
fi

# 2. Start Workers
# `start_worker_if` gates the spawn on availability. First arg is a test command
# whose exit code decides whether to spawn. Missing binaries / unreachable
# backends no longer produce doomed workers with silent stderr.
# Load Mistral API key from vibe env file
[ -f "$HOME/.vibe/.env" ] && export $(grep -v "^#" "$HOME/.vibe/.env" | xargs)

# GEMINI — native agent via gemini-cli
if test -f "$GEMINI_CLI"; then
    echo "Starting native worker: GEMINI"
    nohup node "$ROME_ROOT/dist/src/native_agent.js" \
        --capability GEMINI --model gemini-3-flash-preview \
        --ws-url "$WS_URL/ws" \
        --cli "node $GEMINI_CLI --sandbox false --include-directories $ROME_ROOT --yolo --output-format json -m {MODEL} -p {PROMPT}" \
        --cli-output-format json > "/tmp/rome-worker-GEMINI.log" 2>&1 &
else
    echo "Skipping GEMINI: gemini-cli not found"
fi

# MISTRAL — native agent via vibe.cli
if test -d /home/paul-kane/projects/mistral-cli && command -v python3 >/dev/null 2>&1; then
    echo "Starting native worker: MISTRAL"
    nohup node "$ROME_ROOT/dist/src/native_agent.js" \
        --capability MISTRAL \
        --ws-url "$WS_URL/ws" \
        --cli "env PYTHONPATH=/home/paul-kane/projects/mistral-cli python3 -m vibe.cli.entrypoint --agent auto-approve --output text --max-turns 1 -p" \
        --cli-output-format text > "/tmp/rome-worker-MISTRAL.log" 2>&1 &
else
    echo "Skipping MISTRAL: mistral-cli not found"
fi

# CLAUDE — native agent via claude CLI
if command -v claude >/dev/null 2>&1; then
    echo "Starting native worker: CLAUDE"
    nohup node "$ROME_ROOT/dist/src/native_agent.js" \
        --capability CLAUDE \
        --ws-url "$WS_URL/ws" \
        --cli "claude --dangerously-skip-permissions --output-format json -p" \
        --cli-output-format json > "/tmp/rome-worker-CLAUDE.log" 2>&1 &
else
    echo "Skipping CLAUDE: claude not found"
fi

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
