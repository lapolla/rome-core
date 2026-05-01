import { test, describe } from 'node:test';
import assert from 'node:assert';
import { EventEmitter } from 'events';
import { executeShell } from '../src/shell_executor.js';

describe('executeShell', () => {
  test('returns SUCCESS on exit code 0', async () => {
    const result = await executeShell('t-ok', 'echo hello');
    assert.strictEqual(result.status, 'SUCCESS');
    assert.strictEqual(result.exit_code, 0);
    assert.ok(result.report.includes('hello'));
    assert.ok(result.elapsed_s >= 0);
  });

  test('returns FAILED on non-zero exit code', async () => {
    const result = await executeShell('t-fail', 'exit 1');
    assert.strictEqual(result.status, 'FAILED');
    assert.strictEqual(result.exit_code, 1);
  });

  test('captures stderr in report', async () => {
    const result = await executeShell('t-stderr', 'echo errout >&2');
    assert.ok(result.report.includes('errout'));
  });

  test('captures both stdout and stderr', async () => {
    const result = await executeShell('t-both', 'echo out; echo err >&2');
    assert.ok(result.report.includes('out'));
    assert.ok(result.report.includes('err'));
  });

  test('sets ROME_TASK_ID in subprocess environment', async () => {
    const result = await executeShell('my-task-id', 'echo $ROME_TASK_ID');
    assert.ok(result.report.includes('my-task-id'));
  });

  test('cancel via cancelEmitter kills process and marks FAILED', async () => {
    const emitter = new EventEmitter();
    const promise = executeShell('t-cancel', 'sleep 30', undefined, emitter);
    setTimeout(() => emitter.emit('cancel', 't-cancel'), 100);
    const result = await promise;
    assert.strictEqual(result.status, 'FAILED');
    assert.ok(result.report.includes('[CANCEL]'));
  });

  test('timeout via cancelEmitter kills process and marks FAILED', async () => {
    const emitter = new EventEmitter();
    const promise = executeShell('t-timeout', 'sleep 30', undefined, emitter);
    setTimeout(() => emitter.emit('timeout', 't-timeout'), 100);
    const result = await promise;
    assert.strictEqual(result.status, 'FAILED');
    assert.ok(result.report.includes('[TIMEOUT]'));
  });

  test('truncates report at 4000 chars', async () => {
    const result = await executeShell('t-long', 'python3 -c "print(\'x\' * 10000)"');
    assert.ok(result.report.length <= 4000);
  });

  test('sends progress events via wsSender', async () => {
    const events: any[] = [];
    const sender = async (ev: any) => { events.push(ev); };
    await executeShell('t-progress', 'for i in $(seq 1 20); do echo $i; done', sender);
    assert.ok(events.some(e => e.type === 'progress'));
  });
});
