import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { WebSocketServer, WebSocket } from 'ws';
import * as fs from 'fs';
import { MeshAgent } from '../src/native_agent.js';

/* ------------------------------------------------------------------ */
/* parseSignals — pure signal extraction from LLM output               */
/* ------------------------------------------------------------------ */
describe('MeshAgent.parseSignals', () => {
  const agent = new MeshAgent({ wsUrl: 'ws://localhost:1', token: '', capability: 'GEMMA', model: 'test' });

  test('extracts ROME_SHELL signal', () => {
    const signals = agent.parseSignals('[ROME_SHELL: "ls -la"]');
    assert.strictEqual(signals.length, 1);
    assert.strictEqual(signals[0].type, 'shell');
    assert.strictEqual(signals[0].command, 'ls -la');
  });

  test('extracts ROME_DISPATCH signal', () => {
    const signals = agent.parseSignals('[ROME_DISPATCH: GEMINI "analyze this"]');
    assert.strictEqual(signals.length, 1);
    assert.strictEqual(signals[0].type, 'dispatch');
    assert.strictEqual(signals[0].capability, 'GEMINI');
    assert.strictEqual(signals[0].prompt, 'analyze this');
  });

  test('extracts multiple signals from one text', () => {
    const text = '[ROME_SHELL: "echo hello"]\n[ROME_DISPATCH: MISTRAL "do something"]';
    const signals = agent.parseSignals(text);
    assert.strictEqual(signals.length, 2);
    assert.strictEqual(signals[0].type, 'shell');
    assert.strictEqual(signals[1].type, 'dispatch');
  });

  test('extracts execute_bash fallback format', () => {
    const signals = agent.parseSignals('<execute_bash>git status</execute_bash>');
    assert.strictEqual(signals.length, 1);
    assert.strictEqual(signals[0].type, 'shell');
    assert.strictEqual(signals[0].command, 'git status');
  });

  test('extracts markdown bash block fallback', () => {
    const signals = agent.parseSignals('```bash\nnpm test\n```');
    assert.strictEqual(signals.length, 1);
    assert.strictEqual(signals[0].type, 'shell');
    assert.strictEqual(signals[0].command, 'npm test');
  });

  test('returns empty array for plain text', () => {
    const signals = agent.parseSignals('Just a regular response with no signals.');
    assert.strictEqual(signals.length, 0);
  });

  test('ROME_SHELL takes precedence over markdown bash fallback', () => {
    const text = '[ROME_SHELL: "real command"]\n```bash\nfallback\n```';
    const signals = agent.parseSignals(text);
    assert.ok(signals.every(s => s.command !== 'fallback'));
  });
});

/* ------------------------------------------------------------------ */
/* MeshAgent WS handshake                                              */
/* ------------------------------------------------------------------ */
describe('MeshAgent connect and handshake', () => {
  let wss: WebSocketServer;
  let port: number;
  const agents: MeshAgent[] = [];

  before(async () => {
    wss = new WebSocketServer({ port: 0 });
    await new Promise<void>(resolve => wss.on('listening', resolve));
    port = (wss.address() as any).port;
  });

  after(async () => {
    agents.forEach(a => a.disconnect());
    for (const client of wss.clients) client.terminate();
    await new Promise<void>(resolve => wss.close(() => resolve()));
  });

  test('sends agent_hello on connect', async () => {
    const agent = new MeshAgent({ wsUrl: `ws://127.0.0.1:${port}`, token: '', capability: 'GEMMA', model: 'test' });
    agents.push(agent);
    const hello = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('agent_hello timeout')), 3000);
      wss.once('connection', (ws) => {
        ws.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'agent_hello') { clearTimeout(timeout); resolve(msg); }
        });
      });
      agent.connect();
    });

    assert.strictEqual(hello.type, 'agent_hello');
    assert.ok(hello.payload.capabilities.includes('GEMMA'));
    assert.strictEqual(hello.payload.one_shot, false);
    assert.ok(hello.payload.version);
  });

  test('routes incoming response to pending request', async () => {
    const agent = new MeshAgent({ wsUrl: `ws://127.0.0.1:${port}`, token: '', capability: 'GEMMA', model: 'test' });
    agents.push(agent);
    const result = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('request timeout')), 3000);
      wss.once('connection', (ws) => {
        ws.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'agent_hello') {
            ws.send(JSON.stringify({ type: 'response', request_id: 'test-req-1', ok: true, payload: { result: 'routed' } }));
          }
        });
      });
      (agent as any).pendingRequests.set('test-req-1', (msg: any) => { clearTimeout(timeout); resolve(msg); });
      agent.connect();
    });

    assert.strictEqual(result.ok, true);
    assert.strictEqual(result.payload.result, 'routed');
  });
});

/* ------------------------------------------------------------------ */
/* callCLI — {PROMPT} substitution and model fallback                  */
/* ------------------------------------------------------------------ */
describe('MeshAgent.callCLI', () => {
  test('{PROMPT} is shell-quoted and passed as CLI argument', async () => {
    const agent = new MeshAgent({
      wsUrl: 'ws://localhost:1', token: '', capability: 'MISTRAL', model: '',
      cliCommand: 'printf "%s" {PROMPT}', cliOutputFormat: 'text',
    });
    const result = await (agent as any).callCLI([{ role: 'user', content: "it's alive" }]);
    assert.strictEqual(result, "it's alive");
  });

  test('multi-word prompt is not split by shell', async () => {
    const agent = new MeshAgent({
      wsUrl: 'ws://localhost:1', token: '', capability: 'MISTRAL', model: '',
      cliCommand: 'printf "%s" {PROMPT}', cliOutputFormat: 'text',
    });
    const result = await (agent as any).callCLI([{ role: 'user', content: 'hello world foo bar' }]);
    assert.strictEqual(result, 'hello world foo bar');
  });

  test('retries with next model on quota error', async () => {
    const scriptPath = '/tmp/rome-test-model-fallback.sh';
    fs.writeFileSync(scriptPath, '#!/bin/bash\nif [ "$1" = "model-a" ]; then echo "quota exceeded"; else echo "ALIVE"; fi\n');
    fs.chmodSync(scriptPath, 0o755);

    const agent = new MeshAgent({
      wsUrl: 'ws://localhost:1', token: '', capability: 'GEMINI', model: 'model-a',
      models: ['model-a', 'model-b'],
      cliCommand: `${scriptPath} {MODEL}`, cliOutputFormat: 'text',
    });
    const result = await (agent as any).callCLI([{ role: 'user', content: 'ping' }]);
    assert.strictEqual(result, 'ALIVE');
  });
});
