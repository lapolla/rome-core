#!/bin/bash
pkill -f 'dictator.daemon' 2>/dev/null
sleep 2
cd /home/paul-kane/projects/rome-core
ROME_DAEMON=1 nohup python3 -m dictator.daemon --port 8741 > /tmp/rome-daemon.log 2>&1 &
echo "ROME daemon restarted (PID: $!)"
