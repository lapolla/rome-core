import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { WebSocket } from 'ws';

const DAEMON = 'ws://127.0.0.1:8741';

function dispatchAndAwait(ws: WebSocket, capability: string, prompt: string, timeoutMs = 30000): Promise<string> {
  return new Promise((resolve, reject) => {
    const reqId = `smoke-req-${capability}-${Date.now()}`;
    const t = setTimeout(() => reject(new Error(`${capability} timeout after ${timeoutMs}ms`)), timeoutMs);
    let taskId: string | null = null;

    const handler = (data: Buffer) => {
      try {
        const msg = JSON.parse(data.toString());
        // Capture real task_id from dispatch ACK
        if (msg.type === 'response' && msg.request_id === reqId && msg.ok && msg.payload?.task_id) {
          taskId = msg.payload.task_id;
        }
        // Wait for complete on that task_id
        if (taskId && msg.type === 'event' && msg.event?.task_id === taskId && msg.event?.type === 'complete') {
          clearTimeout(t);
          ws.removeListener('message', handler);
          resolve(msg.event.payload?.status ?? 'UNKNOWN');
        }
      } catch {}
    };
    ws.on('message', handler);
    ws.send(JSON.stringify({
      type: 'command', command: 'dispatch', request_id: reqId,
      payload: { capability, prompt }
    }));
  });
}

describe('Mesh Smoke — one by one', () => {
  let ws: WebSocket;

  before(async () => {
    ws = new WebSocket(DAEMON);
    await new Promise<void>((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
    });
  });

  after(() => ws.close());

  test('SAFE_SHELL', async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'SAFE_SHELL', 'echo ok'), 'SUCCESS');
  });

  test('NATIVE_SHELL', async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'NATIVE_SHELL', 'echo ok'), 'SUCCESS');
  });

  test('GEMINI', { timeout: 60000 }, async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'GEMINI', 'reply with one word: ok', 60000), 'SUCCESS');
  });

  test('MISTRAL', { timeout: 60000 }, async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'MISTRAL', 'reply with one word: ok', 60000), 'SUCCESS');
  });

  test('GEMMA', { timeout: 60000 }, async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'GEMMA', 'reply with one word: ok', 60000), 'SUCCESS');
  });

  test('HAIKU', { timeout: 60000 }, async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'HAIKU', 'reply with one word: ok', 60000), 'SUCCESS');
  });

  test('CLAUDE', { timeout: 120000 }, async () => {
    assert.strictEqual(await dispatchAndAwait(ws, 'CLAUDE', 'reply with one word: ok', 120000), 'SUCCESS');
  });
});
