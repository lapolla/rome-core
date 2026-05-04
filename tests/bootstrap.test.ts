import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { WebSocketServer } from 'ws';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { probe } from '../src/bootstrap.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROME_ROOT = __dirname.includes('dist') 
  ? path.resolve(__dirname, '../..') 
  : path.resolve(__dirname, '..');


describe('probe', () => {
  test('returns true for passing command', () => {
    assert.equal(probe('true', {}), true);
  });

  test('returns false for failing command', () => {
    assert.equal(probe('false', {}), false);
  });

  test('returns false for missing command', () => {
    assert.equal(probe('command_that_does_not_exist_xyzzy', {}), false);
  });
});

describe('bootstrap WS emission', () => {
  test('emits worker_spawn events for spawned and skipped workers', async () => {
    const wss = new WebSocketServer({ port: 0 });
    const port = (wss.address() as { port: number }).port;

    const received: { capability: string; status: string }[] = [];
    wss.on('connection', (ws) => {
      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        if (msg.payload?.event?.type === 'worker_spawn') {
          received.push(msg.payload.event);
        }
      });
    });

    const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'rome-test-'));
    fs.mkdirSync(path.join(tmpRoot, 'dictator'));
    const policy = {
      workers: [
        { capability: 'PROBE_PASS', invocation: 'native_agent_cli', probe: 'true', cli_command: 'echo ok', output_format: 'text' },
        { capability: 'PROBE_FAIL', invocation: 'native_agent_cli', probe: 'false', cli_command: 'echo ok', output_format: 'text' }
      ]
    };
    fs.writeFileSync(path.join(tmpRoot, 'dictator', 'workers.json'), JSON.stringify(policy));

    await new Promise<void>((resolve, reject) => {
      const child = spawn('node', [path.join(ROME_ROOT, 'dist/src/bootstrap.js'), `ws://127.0.0.1:${port}`], {
        env: { ...process.env, ROME_ROOT: tmpRoot },
        stdio: 'ignore',
      });
      child.on('exit', () => setTimeout(resolve, 200));

      child.on('error', reject);
      setTimeout(() => { child.kill(); reject(new Error('bootstrap timeout')); }, 8000);
    });

    wss.close();
    fs.rmSync(tmpRoot, { recursive: true });

    assert.equal(received.length, 2);
    const pass = received.find(e => e.capability === 'PROBE_PASS');
    const fail = received.find(e => e.capability === 'PROBE_FAIL');
    assert.equal(pass?.status, 'spawned');
    assert.equal(fail?.status, 'skipped');
  });
});
