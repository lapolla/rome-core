import { test, describe } from 'node:test';
import assert from 'node:assert';
import { EventBus, TaskRegistry } from '../src/registry.js';
import { WebSocket } from 'ws';

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
