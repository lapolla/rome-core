import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';

describe('Capability Fencing', () => {
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

  test('should block dispatch after worker returns quota error', async () => {
    const workerWs = new WebSocket(`ws://127.0.0.1:${port}`);
    const clientWs = new WebSocket(`ws://127.0.0.1:${port}`);

    try {
      /* 1. Register fake GEMINI worker */
      await new Promise<void>((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('worker register timeout')), 2000);
        workerWs.on('open', () => workerWs.send(JSON.stringify({
          type: 'agent_hello',
          payload: { capabilities: ['GEMINI'], version: '1.0.0', platform: 'linux' }
        })));
        workerWs.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'worker_ack') { clearTimeout(t); resolve(); }
        });
        workerWs.on('error', reject);
      });

      /* Wait for client connection */
      await new Promise<void>((resolve, reject) => {
        if (clientWs.readyState === WebSocket.OPEN) return resolve();
        clientWs.on('open', resolve);
        clientWs.on('error', reject);
      });

      /* 2. Dispatch to GEMINI — fake worker replies with quota error */
      let dispatchedTaskId = '';

      await new Promise<void>((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('first dispatch timeout')), 3000);

        workerWs.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'command' && msg.command === 'dispatch' && !dispatchedTaskId) {
            dispatchedTaskId = msg.payload.task_id;
            workerWs.send(JSON.stringify({
              type: 'event',
              event: {
                type: 'complete',
                task_id: dispatchedTaskId,
                payload: { status: 'FAILED', report: 'TerminalQuotaError: quota will reset after 6h.' }
              }
            }));
          }
        });

        const onMsg = (data: Buffer) => {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'event' && msg.event?.type === 'complete' && msg.event?.task_id === dispatchedTaskId) {
            clearTimeout(t);
            clientWs.removeListener('message', onMsg);
            resolve();
          }
        };
        clientWs.on('message', onMsg);

        clientWs.send(JSON.stringify({
          type: 'command', command: 'dispatch', request_id: 'req-fence-1',
          payload: { capability: 'GEMINI', prompt: 'trigger quota error' }
        }));
      });

      /* 3. Second dispatch to GEMINI must be blocked immediately */
      const blocked = await new Promise<any>((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('gate check timeout')), 2000);
        const onMsg = (data: Buffer) => {
          const msg = JSON.parse(data.toString());
          if (msg.request_id === 'req-fence-2') {
            clearTimeout(t);
            clientWs.removeListener('message', onMsg);
            resolve(msg);
          }
        };
        clientWs.on('message', onMsg);
        clientWs.send(JSON.stringify({
          type: 'command', command: 'dispatch', request_id: 'req-fence-2',
          payload: { capability: 'GEMINI', prompt: 'should be blocked' }
        }));
      });

      assert.strictEqual(blocked.ok, false);
      assert.ok(blocked.error?.includes('unavailable'), `Expected unavailable error, got: ${blocked.error}`);
    } finally {
      workerWs.close();
      clientWs.close();
    }
  });

  test('should not block dispatch for available capabilities', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`);
    try {
      await new Promise<void>((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('timeout')), 3000);
        ws.on('open', () => ws.send(JSON.stringify({
          type: 'command', command: 'native_shell',
          request_id: 'req-avail-1',
          payload: { command: 'echo ok' }
        })));
        ws.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (msg.request_id === 'req-avail-1') {
            clearTimeout(t);
            assert.strictEqual(msg.ok, true);
            resolve();
          }
        });
        ws.on('error', reject);
      });
    } finally {
      ws.close();
    }
  });
});
