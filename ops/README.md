# ROME Dictator Daemon Systemd Service

To enable and start the ROME Dictator Daemon systemd service:

1. Copy `rome-dictator.service` to `/etc/systemd/system/`:
   ```bash
   sudo cp rome-dictator.service /etc/systemd/system/
   ```

2. Reload systemd to pick up the new service file:
   ```bash
   sudo systemctl daemon-reload
   ```

3. Enable the service to start on boot:
   ```bash
   sudo systemctl enable rome-dictator.service
   ```

4. Start the service immediately:
   ```bash
   sudo systemctl start rome-dictator.service
   ```
