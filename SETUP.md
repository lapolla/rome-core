# Setup & Installation

## Prerequisites
- Python 3.11+
- pip

## Dependencies
- websockets (daemon + worker connections)

## Configuration

Before starting, configure your environment using file-based configuration:
- **`dictator/config.json`**: Define your daemon settings such as the port to listen on.
- **`.rome_SOVEREIGN_TOKEN`**: A file containing your secure WebSocket token. Keep this file safe and do not commit it.

## Install
```bash
pip install -r requirements.txt
```

## Start Daemon

### 1. Linux (systemd — system unit)
```ini
# /etc/systemd/system/rome-dictator.service
[Unit]
Description=ROME Dictator Daemon
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m dictator.daemon
WorkingDirectory=/path/to/rome-core
Environment=PYTHONPATH=/path/to/rome-core
Restart=always
RestartSec=5
User=your-user

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now rome-dictator
```

### 2. Linux (systemd — user unit, no sudo)
```bash
mkdir -p ~/.config/systemd/user
# Create ~/.config/systemd/user/rome-dictator.service with the same content
# but use %h for home directory paths
systemctl --user enable --now rome-dictator
```

### 3. Manual (any OS)
```bash
python3 -m dictator.daemon
```

## Start Persistent Workers

Workers connect to the daemon via WebSocket and receive task dispatches.

### Gemini Worker (systemd user unit)
```ini
# ~/.config/systemd/user/rome-gemini-worker.service
[Unit]
Description=ROME Gemini Persistent Worker
After=default.target

[Service]
ExecStart=/usr/bin/python3 %h/projects/rome-core/legions/legion_wrapper.py \
  --mode worker \
  --capabilities GEMINI \
  -- gemini --sandbox false --yolo --output-format json -m gemini-3.1-pro-preview -p
WorkingDirectory=%h/projects/rome-core
Environment=PYTHONPATH=%h/projects/rome-core
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```
```bash
systemctl --user enable --now rome-gemini-worker
```

### Manual Worker Launch
```bash
python3 legions/legion_wrapper.py \
  --mode worker \
  --capabilities GEMINI \
  -- gemini --sandbox false --yolo --output-format json -m gemini-3.1-pro-preview -p
```

## Verify

```bash
# Check daemon health
curl http://127.0.0.1:<PORT>/health

# Check via WS
python3 rome_native.py ping '{}'

# Dashboard
open http://127.0.0.1:<PORT>/dashboard/
```
