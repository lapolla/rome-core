# Setup & Installation

## Prerequisites
- Python 3.11+
- pip

## Dependencies
- fastmcp
- uvicorn
- websockets

## Install
```bash
pip install -r requirements.txt
```

## Start Daemon

You can start the daemon in one of four ways depending on your environment:

### 1. Linux (systemd)
Create a service file `/etc/systemd/system/rome-daemon.service`:
```ini
[Unit]
Description=Rome Core Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 -m dictator.daemon --port 8741
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl enable --now rome-daemon
```

### 2. macOS (launchd)
Create a plist file `~/Library/LaunchAgents/com.rome.daemon.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rome.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>python3</string>
        <string>-m</string>
        <string>dictator.daemon</string>
        <string>--port</string>
        <string>8741</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```
Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.rome.daemon.plist
```

### 3. FreeBSD (rc.d)
Create an rc script `/usr/local/etc/rc.d/rome_daemon`:
```sh
#!/bin/sh
# REQUIRE: DAEMON
# PROVIDE: rome_daemon

. /etc/rc.subr

name="rome_daemon"
rcvar="rome_daemon_enable"
command="/usr/local/bin/python3"
command_args="-m dictator.daemon --port 8741 &"

load_rc_config $name
run_rc_command "$1"
```
Enable and start:
```bash
sysrc rome_daemon_enable="YES"
service rome_daemon start
```

### 4. Any OS (tmux/screen)
Start manually in a terminal multiplexer:
```bash
tmux new -s rome -d "python3 -m dictator.daemon --port 8741"
# OR
screen -dmS rome python3 -m dictator.daemon --port 8741
```
