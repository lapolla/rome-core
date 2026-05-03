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
# 2. Spawn workers via policy (dictator/workers.json)
echo "Bootstrapping workers from policy..."
export GEMINI_CLI
node "$ROME_ROOT/dist/src/bootstrap.js" "$WS_URL"

# ... 
ROME_VERSION=$(grep '"version":' "$ROME_ROOT/package.json" | cut -d'"' -f4)
echo "ROME v$ROME_VERSION Mesh restarted."
