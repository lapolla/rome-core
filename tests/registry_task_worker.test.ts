import { test, describe } from 'node:test';
import assert from 'node:assert';
import { TaskRegistry, WorkerRegistry } from '../src/registry.js';
import { WebSocket } from 'ws';
import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';

/* ------------------------------------------------------------------ */
/* TaskRegistry                                                         */
/* ------------------------------------------------------------------ */
describe('TaskRegistry', () => {
  test('register creates task with pending status', () => {
    const reg = new TaskRegistry();
    reg.register('t1', 'GEMINI', 'do something', undefined, 'my goal', 'my intent');
    const task = reg.get('t1');
    assert.ok(task);
    assert.strictEqual(task!.status, 'pending');
    assert.strictEqual(task!.capability, 'GEMINI');
    assert.strictEqual(task!.goal, 'my goal');
    assert.strictEqual(task!.intent, 'my intent');
  });

  test('register defaults goal to prompt slice and intent to Autonomous Execution', () => {
    const reg = new TaskRegistry();
    reg.register('t2', 'GEMINI', 'x'.repeat(100));
    const task = reg.get('t2');
    assert.strictEqual(task!.goal, 'x'.repeat(50));
    assert.strictEqual(task!.intent, 'Autonomous Execution');
  });

  test('update changes status and stores report', () => {
    const reg = new TaskRegistry();
    reg.register('t3', 'GEMINI', 'prompt');
    reg.update('t3', 'completed', { report: 'done!' });
    const task = reg.get('t3');
    assert.strictEqual(task!.status, 'completed');
    assert.strictEqual(task!.report, 'done!');
    assert.ok(task!.completed_at);
    assert.strictEqual(task!.progress_percent, 100);
  });

  test('update accumulates session usage', () => {
    const reg = new TaskRegistry();
    reg.register('t4', 'GEMINI', 'prompt');
    reg.update('t4', 'completed', {}, { total_tokens: 100, cost_usd: 0.01 });
    reg.register('t5', 'GEMINI', 'prompt2');
    reg.update('t5', 'completed', {}, { total_tokens: 50, cost_usd: 0.005 });
    const stats = reg.getSessionStats();
    assert.strictEqual(stats.session_worker_tokens, 150);
    assert.ok(Math.abs(stats.session_cost_usd - 0.015) < 0.0001);
  });

  test('update with failed status sets completed_at', () => {
    const reg = new TaskRegistry();
    reg.register('t6', 'GEMINI', 'prompt');
    reg.update('t6', 'failed', { error: 'boom' });
    const task = reg.get('t6');
    assert.strictEqual(task!.status, 'failed');
    assert.ok(task!.completed_at);
  });

  test('update sets completed_at and progress 100 on terminal status', () => {
    const reg = new TaskRegistry();
    reg.register('t7', 'GEMINI', 'prompt');
    reg.update('t7', 'completed', {});
    const task = reg.get('t7');
    assert.ok(task!.completed_at);
    assert.strictEqual(task!.progress_percent, 100);
    assert.strictEqual(task!.status, 'completed');
  });

  test('get returns undefined for unknown task', () => {
    const reg = new TaskRegistry();
    assert.strictEqual(reg.get('nope'), undefined);
  });

  test('getAll returns all registered tasks', () => {
    const reg = new TaskRegistry();
    reg.register('a', 'GEMINI', 'p1');
    reg.register('b', 'GEMINI', 'p2');
    assert.strictEqual(reg.getAll().length, 2);
  });

  test('hydrateFromLog accumulates project usage from JSONL', () => {
    const tmp = path.join(os.tmpdir(), `rome-reg-test-${Date.now()}.jsonl`);
    fs.writeFileSync(tmp, [
      JSON.stringify({ usage: { total_tokens: 200, cost_usd: 0.02 } }),
      JSON.stringify({ usage: { total_tokens: 100, cost_usd: 0.01 } }),
    ].join('\n'));
    const reg = new TaskRegistry();
    reg.hydrateFromLog(tmp);
    const stats = reg.getSessionStats();
    assert.strictEqual(stats.project_total_tokens, 300);
    fs.unlinkSync(tmp);
  });

  test('hydrateFromLog handles missing file gracefully', () => {
    const reg = new TaskRegistry();
    assert.doesNotThrow(() => reg.hydrateFromLog('/nonexistent/path.jsonl'));
  });

  test('hydrateFromLog skips malformed lines', () => {
    const tmp = path.join(os.tmpdir(), `rome-reg-bad-${Date.now()}.jsonl`);
    fs.writeFileSync(tmp, 'not json\n{"usage":{"total_tokens":50,"cost_usd":0.005}}\n{bad}');
    const reg = new TaskRegistry();
    assert.doesNotThrow(() => reg.hydrateFromLog(tmp));
    const stats = reg.getSessionStats();
    assert.strictEqual(stats.project_total_tokens, 50);
    fs.unlinkSync(tmp);
  });
});

/* ------------------------------------------------------------------ */
/* WorkerRegistry                                                       */
/* ------------------------------------------------------------------ */
describe('WorkerRegistry', () => {
  function mockWs() {
    return {} as WebSocket;
  }

  test('register adds worker with uppercased capabilities', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['gemini', 'safe_shell'], '1.0', 'linux', '', false);
    const info = reg.getInfo();
    assert.strictEqual(info.length, 1);
    assert.ok(info[0].capabilities.includes('GEMINI'));
    assert.ok(info[0].capabilities.includes('SAFE_SHELL'));
  });

  test('findWorker returns idle worker matching capability', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['GEMINI'], '1.0', 'linux', '', false);
    assert.strictEqual(reg.findWorker('GEMINI'), ws);
  });

  test('findWorker returns null when no matching capability', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['MISTRAL'], '1.0', 'linux', '', false);
    assert.strictEqual(reg.findWorker('GEMINI'), null);
  });

  test('findWorker returns null when all matching workers are busy', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['GEMINI'], '1.0', 'linux', '', false);
    reg.markBusy(ws, 'task-1');
    assert.strictEqual(reg.findWorker('GEMINI'), null);
  });

  test('markBusy and markIdle toggle worker availability', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['GEMINI'], '1.0', 'linux', '', false);
    reg.markBusy(ws, 'task-x');
    assert.strictEqual(reg.findWorker('GEMINI'), null);
    reg.markIdle(ws, 'task-x');
    assert.strictEqual(reg.findWorker('GEMINI'), ws);
  });

  test('unregister removes worker and returns orphaned task ids', () => {
    const reg = new WorkerRegistry();
    const ws = mockWs();
    reg.register(ws, ['GEMINI'], '1.0', 'linux', '', false);
    reg.markBusy(ws, 'orphan-1');
    reg.markBusy(ws, 'orphan-2');
    const orphaned = reg.unregister(ws);
    assert.deepStrictEqual(orphaned.sort(), ['orphan-1', 'orphan-2']);
    assert.strictEqual(reg.findWorker('GEMINI'), null);
  });
});
