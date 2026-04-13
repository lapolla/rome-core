import { test, describe } from 'node:test';
import assert from 'node:assert';
import { EventBus, TaskRegistry, Blackboard, MeshReducer } from '../src/registry.js';
import { WebSocket } from 'ws';

describe('Blackboard', () => {
  test('should set and get state', () => {
    const bb = new Blackboard();
    const success = bb.set({ key: 'build_status', value: 'FAILED', caused_by_task: 't1', task_ts: 100 });
    assert.strictEqual(success, true);
    assert.strictEqual(bb.get('build_status'), 'FAILED');
    assert.strictEqual(bb.getMeta('build_status')?.caused_by_task, 't1');
  });

  test('should reject updates from older tasks (optimistic concurrency)', () => {
    const bb = new Blackboard();
    bb.set({ key: 'status', value: 'NEW', caused_by_task: 't2', task_ts: 200 });
    const success = bb.set({ key: 'status', value: 'OLD', caused_by_task: 't1', task_ts: 100 });
    assert.strictEqual(success, false);
    assert.strictEqual(bb.get('status'), 'NEW');
    assert.strictEqual(bb.getMeta('status')?.caused_by_task, 't2');
  });

  test('should shallow merge object values (atomic patching)', () => {
    const bb = new Blackboard();
    bb.set({ key: 'config', value: { a: 1, b: 2 }, caused_by_task: 't1', task_ts: 100 });
    bb.set({ key: 'config', value: { b: 3, c: 4 }, caused_by_task: 't2', task_ts: 200 });
    assert.deepStrictEqual(bb.get('config'), { a: 1, b: 3, c: 4 });
  });
});

describe('EventBus', () => {
  test('should store and replay history to new subscribers', async () => {
    const bus = new EventBus();
    let received = false;
    const mockWs = {
      readyState: 1,
      send: (data: string) => {
        const msg = JSON.parse(data);
        if (msg.type === 'event' && msg.event.payload.test === 1) {
          received = true;
        }
      }
    } as any;

    bus.broadcast({ type: 'test_event', task_id: '123', payload: { test: 1 } });
    bus.subscribe(mockWs);
    assert.strictEqual(received, true);
  });

  test('should broadcast new events to subscribers', async (t) => {
    const bus = new EventBus();
    let receivedCount = 0;
    const mockWs = {
      readyState: 1,
      send: () => { receivedCount++; }
    } as any;

    bus.subscribe(mockWs);
    bus.broadcast({ type: 'live_event', task_id: '456', payload: {} });
    assert.strictEqual(receivedCount, 1);
  });
});

describe('TaskRegistry', () => {
  test('should register and update tasks', () => {
    const registry = new TaskRegistry();
    registry.register('task-1', 'GEMINI', 'prompt', undefined, 'goal', 'intent');
    
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
      ts: 100
    };
    const update = reducer.reduce(task);
    assert.strictEqual(update?.key, 'build_status');
    assert.strictEqual(update?.value, 'FAILED');
    assert.strictEqual(update?.caused_by_task, 't1');
  });

  test('should reduce lint success report to CLEAN status', () => {
    const reducer = new MeshReducer();
    const task: any = {
      task_id: 't2',
      capability: 'SAFE_SHELL',
      prompt: 'npm run lint',
      report: '0 problems found',
      ts: 200
    };
    const update = reducer.reduce(task);
    assert.strictEqual(update?.key, 'lint_status');
    assert.strictEqual(update?.value, 'CLEAN');
  });
});
