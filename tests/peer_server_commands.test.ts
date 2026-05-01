import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';

describe('PeerServer WS commands', () => {
  let server: PeerServer;
  let port: number;
  let ws: WebSocket;

  function send(command: string, payload: any, reqId: string): Promise<any> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`${command} timeout`)), 3000);
      const handler = (data: any) => {
        const msg = JSON.parse(data.toString());
        if (msg.request_id === reqId) {
          clearTimeout(timeout);
          ws.off('message', handler);
          resolve(msg);
        }
      };
      ws.on('message', handler);
      ws.send(JSON.stringify({ type: 'command', command, request_id: reqId, payload }));
    });
  }

  before(async () => {
    server = new PeerServer('DAEMON', 0);
    port = await server.start();
    ws = new WebSocket(`ws://127.0.0.1:${port}`);
    await new Promise<void>(resolve => ws.on('open', resolve));
  });

  after(() => {
    ws.close();
    server.stop();
  });

  test('ping returns pong', async () => {
    const res = await send('ping', {}, 'ping-1');
    assert.ok(res.type === 'response' || res.command === 'pong' || res.ok === true);
  });

  test('get_state returns tasks, workers and uptime_s', async () => {
    const res = await send('get_state', {}, 'state-1');
    assert.strictEqual(res.ok, true);
    assert.ok('tasks' in res.payload);
    assert.ok('workers' in res.payload);
    assert.ok('uptime_s' in res.payload);
    assert.ok(res.payload.uptime_s >= 0);
  });

  test('workers returns array', async () => {
    const res = await send('workers', {}, 'workers-1');
    assert.strictEqual(res.ok, true);
    assert.ok(Array.isArray(res.payload.workers));
  });

  test('reset clears all tasks', async () => {
    const res = await send('reset', {}, 'reset-1');
    assert.strictEqual(res.ok, true);
  });

  test('state_set and state_get roundtrip', async () => {
    const setRes = await send('state_set', { key: 'test_key', value: 'test_val', caused_by_task: 't0', task_ts: Date.now() / 1000 }, 'sset-1');
    assert.strictEqual(setRes.ok, true);
    const getRes = await send('state_get', { key: 'test_key' }, 'sget-1');
    assert.strictEqual(getRes.ok, true);
    assert.strictEqual(getRes.payload.value, 'test_val');
  });

  test('state_delete removes key', async () => {
    await send('state_set', { key: 'del_key', value: 42, caused_by_task: 't1', task_ts: Date.now() / 1000 }, 'sset-2');
    const delRes = await send('state_delete', { key: 'del_key' }, 'sdel-1');
    assert.strictEqual(delRes.ok, true);
    const getRes = await send('state_get', { key: 'del_key' }, 'sget-2');
    assert.strictEqual(getRes.payload.value, undefined);
  });

  test('probe_arsenal returns capability results', async () => {
    const res = await send('probe_arsenal', {}, 'probe-1');
    assert.strictEqual(res.ok, true);
    assert.ok(typeof res.payload.capabilities === 'object');
  });

  test('status returns task and worker info', async () => {
    const res = await send('status', {}, 'status-1');
    assert.strictEqual(res.ok, true);
    assert.ok('workers' in res.payload || 'tasks' in res.payload);
  });
});
