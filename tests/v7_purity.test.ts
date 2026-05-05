import { test, describe } from 'node:test';
import assert from 'node:assert';
import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.cwd();
const WS_URL = 'ws://127.0.0.1:8741';

describe('ROME v7 Purity & Shredder', () => {
  
  test('Surgical Await: Returns only the Marrow', async () => {
    const ws = new WebSocket(WS_URL);
    await new Promise(r => ws.on('open', r));

    const getResponse = () => new Promise(resolve => {
      const cb = (data: any) => {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'response') {
          ws.off('message', cb);
          resolve(msg);
        }
      };
      ws.on('message', cb);
    });

    // 1. Dispatch a simple ping
    ws.send(JSON.stringify({
      type: 'command',
      command: 'dispatch',
      payload: { capability: 'SAFE_SHELL', prompt: 'echo "purity test"' }
    }));

    const dispatchMsg: any = await getResponse();
    const taskId = dispatchMsg.payload.task_id;

    // 2. Await the result
    ws.send(JSON.stringify({
      type: 'command',
      command: 'await',
      payload: { task_id: taskId }
    }));

    const awaitMsg: any = await getResponse();
    const task = awaitMsg.payload.tasks[0];

    // VERIFY: Only task_id, status, and report are returned
    const keys = Object.keys(task).sort();
    assert.deepStrictEqual(keys, ['report', 'status', 'task_id'], 'Await leaked extra JSON shit');
    assert.strictEqual(task.status, 'completed');
    
    ws.close();
  });

  test('Leave No Trace: Shredder deletes empty barracks', async () => {
    const ws = new WebSocket(WS_URL);
    await new Promise(r => ws.on('open', r));

    const getResponse = () => new Promise(resolve => {
      const cb = (data: any) => {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'response') {
          ws.off('message', cb);
          resolve(msg);
        }
      };
      ws.on('message', cb);
    });

    ws.send(JSON.stringify({
      type: 'command',
      command: 'dispatch',
      payload: { capability: 'SAFE_SHELL', prompt: 'echo "shred test" > leaked_file.txt' }
    }));

    const dispatchMsg: any = await getResponse();
    const taskId = dispatchMsg.payload.task_id;

    // Await completion
    ws.send(JSON.stringify({ type: 'command', command: 'await', payload: { task_id: taskId } }));
    await getResponse();

    // VERIFY: The folder in legions/ is GONE
    const taskDir = path.join(ROME_ROOT, 'legions', taskId);
    assert.strictEqual(fs.existsSync(taskDir), false, 'The Hoarder left a ghost folder behind');
    
    ws.close();
  });

  test('The Vault: Brain is protected in .rome/', () => {
    assert.ok(fs.existsSync(path.join(ROME_ROOT, '.rome', 'state.json')), 'Global State is missing from the Vault');
    assert.ok(fs.existsSync(path.join(ROME_ROOT, '.rome', 'memory')), 'Brain Memory is missing from the Vault');
    assert.ok(fs.existsSync(path.join(ROME_ROOT, '.rome', 'cache')), 'Semantic Cache is missing from the Vault');
  });

});
