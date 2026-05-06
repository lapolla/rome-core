import WebSocket from 'ws';

const wsUrl = process.env.ROME_WS_URL || 'ws://127.0.0.1:8741/ws';
const timeoutMs = 5000;

function generateRequestId(): string {
  return `cmd-${Math.random().toString(36).substring(2, 11)}`;
}

function main(): void {
  const [, , command, jsonPayload] = process.argv;

  if (!command) {
    console.error('Usage: node rome_cmd.js <command> [json_payload]');
    process.exit(1);
  }

  let payload: unknown;
  try {
    payload = jsonPayload ? JSON.parse(jsonPayload) : {};
  } catch (err) {
    console.error('Invalid JSON payload:', err);
    process.exit(1);
  }

  const requestId = generateRequestId();
  const message = {
    type: 'command',
    command,
    request_id: requestId,
    payload,
  };

  const ws = new WebSocket(wsUrl);
  let timeoutId: ReturnType<typeof setTimeout>;
  let resolved = false;

  ws.on('open', () => {
    ws.send(JSON.stringify(message));
  });

  ws.on('message', (data) => {
    try {
      const response = JSON.parse(data.toString());
      if (response.request_id === requestId) {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeoutId);
          console.log(JSON.stringify(response, null, 2));
          ws.close();
          process.exit(0);
        }
      }
    } catch (err) {
      // Ignore non-JSON or non-matching messages
    }
  });

  ws.on('error', (err) => {
    if (!resolved) {
      console.error('WebSocket error:', err.message);
      process.exit(1);
    }
  });

  ws.on('close', () => {
    if (!resolved) {
      console.error('WebSocket closed before response');
      process.exit(1);
    }
  });

  timeoutId = setTimeout(() => {
    if (!resolved) {
      resolved = true;
      console.error('Timeout waiting for response');
      ws.close();
      process.exit(1);
    }
  }, timeoutMs);
}

main();
