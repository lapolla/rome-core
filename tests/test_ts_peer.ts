import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';
import * as assert from 'assert';

const TOKEN = "ROME_SECURE_TOKEN";

async function waitMessage(ws: WebSocket, predicate: (msg: any) => boolean, timeout: number = 10000): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ws.removeListener('message', listener);
      reject(new Error('Timeout waiting for message'));
    }, timeout);

    const listener = (data: any) => {
      const msg = JSON.parse(data.toString());
      if (predicate(msg)) {
        clearTimeout(timer);
        ws.removeListener('message', listener);
        resolve(msg);
      }
    };

    ws.on('message', listener);
  });
}

async function runTest() {
  console.log("Starting PeerServer test...");
  const server = new PeerServer('GEMINI', 0);
  server.start();
  
  const port = server.getPort();
  const uri = `ws://127.0.0.1:${port}?token=${TOKEN}`;
  const ws = new WebSocket(uri);

  try {
    // 1. Handshake
    const hello = await waitMessage(ws, m => m.type === 'daemon_hello');
    assert.strictEqual(hello.capabilities[0], 'GEMINI');
    console.log("Handshake OK");

    // 2. Ping
    ws.send(JSON.stringify({
      type: 'command',
      command: 'ping',
      request_id: 'ping-1',
      payload: {}
    }));
    const pong = await waitMessage(ws, m => m.request_id === 'ping-1');
    assert.strictEqual(pong.payload.pong, true);
    console.log("Ping OK");

    // 3. Dispatch
    const task_id = `ts-test-${Math.random().toString(36).substring(7)}`;
    ws.send(JSON.stringify({
      type: 'command',
      command: 'dispatch',
      request_id: 'disp-1',
      payload: {
        task_id,
        capability: 'GEMINI',
        prompt: 'echo hello from TS'
      }
    }));
    const dispResp = await waitMessage(ws, m => m.request_id === 'disp-1');
    assert.strictEqual(dispResp.ok, true);
    console.log("Dispatch accepted");

    // 4. Wait for completion event
    console.log("Waiting for completion event...");
    const complete = await waitMessage(ws, m => m.type === 'event' && m.event.type === 'complete' && m.event.task_id === task_id, 30000);
    assert.strictEqual(complete.event.payload.ok, true);
    console.log("Task completed successfully");

  } catch (e) {
    console.error("Test failed:", e);
    process.exit(1);
  } finally {
    ws.close();
    server.stop();
    console.log("Test finished");
  }
}

runTest();
