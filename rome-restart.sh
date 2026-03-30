#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
pkill -f 'dictator.daemon' 2>/dev/null
sleep 2
cd "$SCRIPT_DIR"
nohup python3 -m dictator.daemon --port 8741 > /tmp/rome-daemon.log 2>&1 &
echo "ROME daemon restarted (PID: $!)"

sleep 2 # wait for daemon to bind
chmod +x "$SCRIPT_DIR/rome-start-workers.sh"
"$SCRIPT_DIR/rome-start-workers.sh"
