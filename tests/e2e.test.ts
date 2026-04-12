import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';

describe('ROME E2E Mesh Dispatch', () => {
  let server: PeerServer;
  let port: number;

  before(async () => {
    server = new PeerServer('DAEMON', 0);
    await server.start();
    port = server.getPort();
  });

  after(() => {
    server.stop();
  });

  test('should dispatch native_shell task and receive complete event', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=ROME_V4_SECURE_TOKEN`);
    
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('E2E Timeout')), 5000);
      let taskId: string;

      ws.on('open', () => {
        ws.send(JSON.stringify({
          type: 'command',
          command: 'native_shell',
          request_id: 'req-1',
          payload: { command: 'echo "hello e2e"' }
        }));
      });

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        console.log('E2E Msg:', msg.type, msg.command || msg.event?.type || '');
        
        if (msg.type === 'response' && msg.request_id === 'req-1') {
          assert.strictEqual(msg.ok, true);
          if (!taskId) taskId = msg.payload.task_id;
        }

        if (msg.type === 'event' && msg.event?.type === 'dispatch_start') {
           taskId = msg.event.task_id;
        }

        if (msg.type === 'event' && msg.event?.type === 'complete') {
          console.log('Complete Event for:', msg.event.task_id);
          if (msg.event.task_id === taskId) {
            assert.strictEqual(msg.event.payload.status, 'SUCCESS');
            assert.ok(msg.event.payload.report.includes('hello e2e'));
            clearTimeout(timeout);
            ws.close();
            resolve();
          }
        }
      });

      ws.on('error', reject);
    });
  });
});
