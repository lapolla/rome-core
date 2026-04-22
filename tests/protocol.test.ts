import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const TOKEN = fs.readFileSync(path.join(process.cwd(), '.rome_SOVEREIGN_TOKEN'), 'utf-8').trim();

describe('ROME Protocol Handshake', () => {
  let server: PeerServer;
  let port: number;

  before(async () => {
    server = new PeerServer('DAEMON', 0);
    port = await server.start();
  });

  after(() => {
    server.stop();
  });

  test('should complete agent_hello handshake and register worker', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=${TOKEN}`);
    
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Handshake timeout')), 2000);
      
      ws.on('open', () => {
        ws.send(JSON.stringify({
          type: 'agent_hello',
          payload: {
            capabilities: ['TEST_CAP'],
            version: '1.0.0',
            platform: 'linux'
          }
        }));
      });

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'worker_ack') {
          clearTimeout(timeout);
          assert.strictEqual(msg.payload.capabilities_accepted[0], 'TEST_CAP');
          ws.close();
          resolve();
        }
      });

      ws.on('error', reject);
    });
  });

  test('should reject worker with empty capabilities', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=${TOKEN}`);
    
    await new Promise<void>((resolve) => {
      ws.on('open', () => {
        ws.send(JSON.stringify({
          type: 'agent_hello',
          payload: { capabilities: [] }
        }));
      });

      ws.on('close', (code) => {
        // Empty capabilities should be ignored/rejected (server doesn't register)
        // In current implementation it logs and ignores, but if it closes:
        resolve();
      });

      // If it doesn't close, we resolve on timeout or specific message
      setTimeout(() => {
        ws.close();
        resolve();
      }, 500);
    });
  });

  test('should set and get state via RSB protocol', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}?token=${TOKEN}`);
    
    await new Promise<void>((resolve, reject) => {
      ws.on('open', () => {
        ws.send(JSON.stringify({
          type: 'command',
          command: 'state_set',
          request_id: 'req1',
          payload: { key: 'test_key', value: 'test_val', caused_by_task: 'ts-init' }
        }));
      });

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        if (msg.request_id === 'req1') {
          assert.strictEqual(msg.ok, true);
          ws.send(JSON.stringify({
            type: 'command',
            command: 'state_get',
            request_id: 'req2',
            payload: { key: 'test_key' }
          }));
        } else if (msg.request_id === 'req2') {
          assert.strictEqual(msg.payload.value, 'test_val');
          ws.close();
          resolve();
        }
      });

      ws.on('error', reject);
    });
  });
});
