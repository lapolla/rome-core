import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';

describe('ROME Protocol Handshake', () => {
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

  test('should complete agent_hello handshake and register worker', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=ROME_V4_SECURE_TOKEN`);
    
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Handshake timeout')), 5000);
      
      ws.on('open', () => {
        console.log('WS Open, sending agent_hello');
        ws.send(JSON.stringify({
          type: 'agent_hello',
          payload: {
            capabilities: ['TEST_CAP'],
            version: '6.0.0',
            platform: 'test',
            peer_url: 'ws://127.0.0.1:9999'
          }
        }));
      });

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        console.log('Received message:', msg.type);
        if (msg.type === 'worker_ack') {
          assert.strictEqual(msg.ok, true);
          assert.deepStrictEqual(msg.payload.capabilities_accepted, ['TEST_CAP']);
          clearTimeout(timeout);
          ws.close();
          resolve();
        }
      });

      ws.on('error', (err) => {
        console.error('WS Error:', err);
        clearTimeout(timeout);
        reject(err);
      });
    });
  });

  test('should reject worker with empty capabilities', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=ROME_V4_SECURE_TOKEN`);
    
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => resolve(), 1000); // Expecting NO worker_ack
      
      ws.on('open', () => {
        ws.send(JSON.stringify({
          type: 'agent_hello',
          payload: { capabilities: [] }
        }));
      });

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'worker_ack') {
          clearTimeout(timeout);
          reject(new Error('Should not have received worker_ack for empty caps'));
        }
      });
    });
    ws.close();
  });
});
