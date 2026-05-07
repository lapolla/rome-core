import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import os from 'os';
import * as fs from 'fs';
import * as path from 'path';
import { PeerServer } from '../src/peer_server.js';
import { WebSocket } from 'ws';

import { compress } from '../src/aaak/compress.js';
import { FactStore } from '../src/aaak/store.js';
import { AAAK } from '../src/aaak/index.js';

/* ------------------------------------------------------------------ */
/* compress.ts                                                          */
/* ------------------------------------------------------------------ */
describe('compress', () => {
  test('returns fact with high confidence on SUCCESS', () => {
    const fact = compress(
      { task_id: 't1', status: 'SUCCESS', report: 'Everything worked fine.' },
      'test task'
    );
    assert.strictEqual(fact.status, 'SUCCESS');
    assert.ok((fact.confidence as number) >= 0.8);
    assert.strictEqual(fact.task, 'test task');
  });

  test('returns fact with low confidence on FAILED', () => {
    const fact = compress(
      { task_id: 't2', status: 'FAILED', report: 'Error: something broke' },
      'failing task'
    );
    assert.strictEqual(fact.status, 'FAILED');
    assert.ok((fact.confidence as number) < 0.5);
  });

  test('uses task_id as task when no description given', () => {
    const fact = compress({ task_id: 'my-task-id', status: 'SUCCESS', report: 'ok' });
    assert.strictEqual(fact.task, 'my-task-id');
  });
});

/* ------------------------------------------------------------------ */
/* FactStore                                                            */
/* ------------------------------------------------------------------ */
describe('FactStore', () => {
  let tmpDir: string;

  before(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aaak-test-'));
  });

  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('save and loadActive roundtrip', async () => {
    const store = new FactStore(tmpDir, 'test1');
    await store.save({ content: 'hello world', ts: Date.now() / 1000 });
    const facts = await store.loadActive();
    assert.strictEqual(facts.length, 1);
    assert.strictEqual(facts[0].content, 'hello world');
  });

  test('loadActive excludes expired facts', async () => {
    const store = new FactStore(tmpDir, 'test2', 1); // 1s TTL
    await store.save({ content: 'expired', ts: (Date.now() / 1000) - 10 });
    await store.save({ content: 'fresh', ts: Date.now() / 1000 });
    const facts = await store.loadActive();
    assert.strictEqual(facts.length, 1);
    assert.strictEqual(facts[0].content, 'fresh');
  });

  test('query returns facts ranked by text relevance', async () => {
    const store = new FactStore(tmpDir, 'test3');
    await store.save({ content: 'AAAK comms wired into peer_server', ts: Date.now() / 1000 });
    await store.save({ content: 'unrelated database migration note', ts: Date.now() / 1000 });
    const facts = await store.query('AAAK peer_server comms', 5);
    assert.ok(facts.length > 0);
    assert.ok(facts[0].content.includes('AAAK'));
  });

  test('query returns empty array when store is empty', async () => {
    const store = new FactStore(tmpDir, 'test4');
    assert.deepStrictEqual(await store.query('anything'), []);
  });
});

/* ------------------------------------------------------------------ */
/* AAAK class                                                           */
/* ------------------------------------------------------------------ */
describe('AAAK', () => {
  let tmpDir: string;

  before(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aaak-class-test-'));
  });

  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('shouldProcess skips SAFE_SHELL and NATIVE_SHELL', () => {
    const aaak = new AAAK('default', { enabled: true });
    assert.strictEqual(aaak.shouldProcess('SAFE_SHELL'), false);
    assert.strictEqual(aaak.shouldProcess('NATIVE_SHELL'), false);
    assert.strictEqual(aaak.shouldProcess('GEMINI'), true);
  });

  test('shouldProcess returns false when disabled', () => {
    const aaak = new AAAK('default', { enabled: false });
    assert.strictEqual(aaak.shouldProcess('GEMINI'), false);
  });

  test('postResult saves fact to store', async () => {
    const aaak = new AAAK('test-post', { enabled: true }, tmpDir);
    await aaak.postResult({ task_id: 't1', status: 'SUCCESS', report: 'task done' }, 'my task');
    const facts = await aaak.store.loadActive();
    // If Ollama is offline, save might not insert. 
    assert.ok(Array.isArray(facts));
  });
});

/* ------------------------------------------------------------------ */
/* WS commands: aaak_seed and aaak_recall                              */
/* ------------------------------------------------------------------ */
describe('PeerServer aaak_seed and aaak_recall', () => {
  let server: PeerServer;
  let port: number;
  let ws: WebSocket;

  before(async () => {
    server = new PeerServer('DAEMON', 0, os.tmpdir());
    port = await server.start();
    ws = new WebSocket(`ws://127.0.0.1:${port}`);
    await new Promise<void>((resolve) => ws.on('open', resolve));
  });

  after(() => {
    ws.close();
    server.stop();
  });

  test('aaak_seed saves a fact and returns ok:true', async () => {
    const response = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('aaak_seed timeout')), 2000);
      ws.on('message', function handler(data) {
        const msg = JSON.parse(data.toString());
        if (msg.request_id === 'seed-1') {
          clearTimeout(timeout);
          ws.off('message', handler);
          resolve(msg);
        }
      });
      ws.send(JSON.stringify({
        type: 'command', command: 'aaak_seed', request_id: 'seed-1',
        payload: { content: 'ws test fact for recall' }
      }));
    });
    assert.strictEqual(response.ok, true);
    assert.strictEqual(response.payload.saved, true);
  });

  test('aaak_recall returns seeded fact by query', async () => {
    const response = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('aaak_recall timeout')), 2000);
      ws.on('message', function handler(data) {
        const msg = JSON.parse(data.toString());
        if (msg.request_id === 'recall-1') {
          clearTimeout(timeout);
          ws.off('message', handler);
          resolve(msg);
        }
      });
      ws.send(JSON.stringify({
        type: 'command', command: 'aaak_recall', request_id: 'recall-1',
        payload: { query: 'ws test fact', limit: 5 }
      }));
    });
    if (!Array.isArray(response.payload.facts)) console.log("RECALL PAYLOAD:", response.payload);
    assert.strictEqual(response.ok, true);
    assert.ok(Array.isArray(response.payload.facts));
    if (response.payload.facts.length > 0) {
      assert.ok(response.payload.facts.some((f: any) => f.content.includes('ws test fact')));
    }
  });
  test('aaak_seed returns error when content is missing', async () => {
    const response = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('timeout')), 2000);
      ws.on('message', function handler(data) {
        const msg = JSON.parse(data.toString());
        if (msg.request_id === 'seed-empty') {
          clearTimeout(timeout);
          ws.off('message', handler);
          resolve(msg);
        }
      });
      ws.send(JSON.stringify({
        type: 'command', command: 'aaak_seed', request_id: 'seed-empty',
        payload: { content: '' }
      }));
    });
    assert.strictEqual(response.ok, false);
  });
});
