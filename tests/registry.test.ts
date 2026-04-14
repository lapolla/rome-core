import { test, describe } from 'node:test';
import assert from 'node:assert';
import { TaskRegistry, MeshReducer, Blackboard, EventBus } from '../src/registry.js';
import { WebSocket } from 'ws';

describe('Blackboard', () => {
  test('should set and get state', () => {
    const bb = new Blackboard();
    const success = bb.set({ key: 'test', value: 'val', caused_by_task: 't1', task_ts: 100 });
    assert.strictEqual(success, true);
    assert.strictEqual(bb.get('test'), 'val');
  });

  test('should reject updates from older tasks (optimistic concurrency)', () => {
    const bb = new Blackboard();
    bb.set({ key: 'test', value: 'new', caused_by_task: 't2', task_ts: 200 });
    const success = bb.set({ key: 'test', value: 'old', caused_by_task: 't1', task_ts: 100 });
    assert.strictEqual(success, false);
    assert.strictEqual(bb.get('test'), 'new');
  });

  test('should shallow merge object values (atomic patching)', () => {
    const bb = new Blackboard();
    bb.set({ key: 'config', value: { a: 1 }, caused_by_task: 't1', task_ts: 100 });
    bb.set({ key: 'config', value: { b: 2 }, caused_by_task: 't2', task_ts: 200 });
    const val = bb.get('config');
    assert.strictEqual(val.a, 1);
    assert.strictEqual(val.b, 2);
  });
});

describe('EventBus', () => {
  test('should store and replay history to new subscribers', async () => {
    const bus = new EventBus();
    bus.broadcast({ type: 'test_event', task_id: 't1', payload: { x: 1 } });
    
    let received = false;
    const listener = (ev: any) => {
      if (ev.type === 'test_event') received = true;
    };
    
    bus.subscribe(listener);
    assert.strictEqual(received, true);
  });

  test('should broadcast new events to subscribers', () => {
    const bus = new EventBus();
    let count = 0;
    bus.subscribe(() => count++);
    bus.broadcast({ type: 'e1', task_id: '', payload: {} });
    bus.broadcast({ type: 'e2', task_id: '', payload: {} });
    assert.strictEqual(count, 2);
  });
});

describe('TaskRegistry', () => {
  test('should register and update tasks', () => {
    const registry = new TaskRegistry();
    registry.register('task-1', 'TEST', 'prompt', undefined, 'goal');
    
    const task = registry.get('task-1');
    assert.strictEqual(task?.status, 'pending');
    assert.strictEqual(task?.goal, 'goal');

    registry.update('task-1', 'completed', { report: 'done' }, { 
      total_tokens: 100, 
      cost_usd: 0.01, 
      model: 'm', 
      prompt_tokens: 50, 
      completion_tokens: 50 
    });
    
    const updated = registry.get('task-1');
    assert.strictEqual(updated?.status, 'completed');
    assert.strictEqual(updated?.report, 'done');
    
    const stats = registry.getSessionStats();
    assert.strictEqual(stats.session_worker_tokens, 100);
    assert.strictEqual(stats.session_cost_usd, 0.01);
  });
});

describe('MeshReducer', () => {
  test('should reduce build failure report to FAILED status', () => {
    const reducer = new MeshReducer();
    const task: any = {
      task_id: 't1',
      capability: 'TEST',
      prompt: 'npm test',
      report: 'Tests failed: 1 error found',
      status: 'completed',
      ts: 100
    };
    const update = reducer.reduce(task);
    assert.strictEqual(update?.key, 'build_status');
    assert.strictEqual(update?.value.status, 'FAILED');
    assert.strictEqual(update?.caused_by_task, 't1');
  });

  test('should reduce lint success report to CLEAN status', () => {
    const reducer = new MeshReducer();
    const task: any = {
      task_id: 't2',
      capability: 'SAFE_SHELL',
      prompt: 'npm run lint',
      report: '0 problems found',
      status: 'completed',
      ts: 200
    };
    const update = reducer.reduce(task);
    assert.strictEqual(update?.key, 'lint_status');
    assert.strictEqual(update?.value.status, 'CLEAN');
  });
});
