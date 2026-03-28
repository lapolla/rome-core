
import sys
from dictator.ws_client import send_command_sync

try:
    result = send_command_sync("status", {})
    print(result)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
