import { test, describe } from 'node:test';
import assert from 'node:assert';
import { executeTask } from '../src/legion_worker.js';
import * as fs from 'fs';
import * as path from 'path';

describe('ROME v7 Execution Environment', () => {
  test('should pass ROME_WS_URL and ROME_WS_TOKEN to subprocess environment', async () => {
    const taskId = 'test-v7-env-' + Date.now();
    const wsUrl = 'ws://localhost:8741';
    const wsToken = 'test-token-123';
    
    // Command to echo env vars
    const cmd = ['bash', '-c', 'echo "URL=$ROME_WS_URL"; echo "TOKEN=$ROME_WS_TOKEN"'];
    
    const manifest = await executeTask(
      taskId,
      'SAFE_SHELL',
      cmd,
      async () => {}, // no-op uiSender
      undefined,
      undefined,
      wsUrl,
      wsToken
    );

    assert.strictEqual(manifest.status, 'SUCCESS');
    assert.ok(manifest.report.includes(`URL=${wsUrl}`), `Report should contain URL=${wsUrl}, got: ${manifest.report}`);
    assert.ok(manifest.report.includes(`TOKEN=${wsToken}`), `Report should contain TOKEN=${wsToken}, got: ${manifest.report}`);
  });

  test('should replace {ROME_WS_URL} and {ROME_WS_TOKEN} in command arguments', async () => {
    const taskId = 'test-v7-replace-' + Date.now();
    const wsUrl = 'ws://localhost:8741';
    const wsToken = 'test-token-456';
    
    // Command that uses tokens in args
    const cmd = ['echo', 'URL={ROME_WS_URL}', 'TOKEN={ROME_WS_TOKEN}'];
    
    const manifest = await executeTask(
      taskId,
      'SAFE_SHELL',
      cmd,
      async () => {},
      undefined,
      undefined,
      wsUrl,
      wsToken
    );

    assert.strictEqual(manifest.status, 'SUCCESS');
    assert.ok(manifest.report.includes(`URL=${wsUrl}`), `Report should contain URL=${wsUrl}, got: ${manifest.report}`);
    assert.ok(manifest.report.includes(`TOKEN=${wsToken}`), `Report should contain TOKEN=${wsToken}, got: ${manifest.report}`);
  });
});
