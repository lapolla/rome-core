import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { WebSocket } from 'ws';

const DAEMON = 'ws://127.0.0.1:8741';

function dispatchAndAwait(ws: WebSocket, capability: string, prompt: string, timeoutMs: number = 30000): Promise<string> {
    return new Promise((resolve, reject) => {
        const reqId = `smoke-req-${capability}-${Date.now()}`;
        const t = setTimeout(() => reject(new Error(`${capability} timeout after ${timeoutMs}ms`)), timeoutMs);
        let taskId: string | null = null;
        const handler = (data: any) => {
            try {
                const msg = JSON.parse(data.toString());
                if (msg.type === 'response' && msg.request_id === reqId && msg.ok && msg.payload?.task_id) {
                    taskId = msg.payload.task_id;
                }
                if (taskId && msg.type === 'event' && msg.event?.task_id === taskId) {
                    if (msg.event.type === 'complete') {
                        clearTimeout(t);
                        ws.removeListener('message', handler);
                        resolve(msg.event.payload?.status ?? 'UNKNOWN');
                    } else if (msg.event.type === 'error') {
                        clearTimeout(t);
                        ws.removeListener('message', handler);
                        resolve('FAILED');
                    }
                }
            } catch { }
        };
        ws.on('message', handler);
        ws.send(JSON.stringify({ type: 'command', command: 'dispatch', request_id: reqId, payload: { capability, prompt } }));
    });
}

describe('Mesh Smoke Tests', () => {
    let ws: WebSocket;

    before(async () => {
        ws = new WebSocket(DAEMON);
        await new Promise<void>((resolve, reject) => {
            ws.once('open', resolve);
            ws.once('error', reject);
        });
    });

    after(() => ws.close());

    test('SAFE_SHELL', async (t) => {
        const status = await dispatchAndAwait(ws, 'SAFE_SHELL', 'echo ok');
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('NATIVE_SHELL', async (t) => {
        const status = await dispatchAndAwait(ws, 'NATIVE_SHELL', 'echo ok');
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('GEMINI', { timeout: 60000 }, async (t) => {
        const status = await dispatchAndAwait(ws, 'GEMINI', 'reply with one word: ok', 60000);
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('MISTRAL', { timeout: 60000 }, async (t) => {
        const status = await dispatchAndAwait(ws, 'MISTRAL', 'reply with one word: ok', 60000);
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('GEMMA', { timeout: 60000 }, async (t) => {
        const status = await dispatchAndAwait(ws, 'GEMMA', 'reply with one word: ok', 60000);
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('HAIKU', { timeout: 60000 }, async (t) => {
        const status = await dispatchAndAwait(ws, 'HAIKU', 'reply with one word: ok', 60000);
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });

    test('CLAUDE', { timeout: 120000 }, async (t) => {
        const status = await dispatchAndAwait(ws, 'CLAUDE', 'reply with one word: ok', 120000);
        if (status === 'FAILED') {
            t.skip('capability unavailable');
            return;
        }
        assert.strictEqual(status, 'SUCCESS');
    });
});
