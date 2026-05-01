import { test, describe } from 'node:test';
import assert from 'node:assert';
import { probeArsenal } from '../src/arsenal_probe.js';

describe('probeArsenal', () => {
  test('non-llm capability is always available', async () => {
    const results = await probeArsenal({ SAFE_SHELL: { type: 'shell' } });
    assert.strictEqual(results.SAFE_SHELL.available, true);
    assert.strictEqual(results.SAFE_SHELL.reason, 'in-process');
  });

  test('llm capability with no binary args is unavailable', async () => {
    const results = await probeArsenal({ MYSTERY: { type: 'llm', args: [] } });
    assert.strictEqual(results.MYSTERY.available, false);
    assert.ok(results.MYSTERY.reason.includes('no binary'));
  });

  test('llm capability with missing binary is unavailable', async () => {
    const results = await probeArsenal({
      FAKE: { type: 'llm', args: ['/nonexistent/binary/path'] }
    });
    assert.strictEqual(results.FAKE.available, false);
    assert.ok(results.FAKE.reason.includes('binary not found'));
  });

  test('llm capability with valid binary on PATH is available', async () => {
    const results = await probeArsenal({
      NODE_CAP: { type: 'llm', args: ['node', '--version'] }
    });
    assert.strictEqual(results.NODE_CAP.available, true);
    assert.ok(results.NODE_CAP.binary);
  });

  test('returns results for all capabilities', async () => {
    const results = await probeArsenal({
      A: { type: 'shell' },
      B: { type: 'llm', args: [] },
      C: { type: 'llm', args: ['node'] }
    });
    assert.ok('A' in results);
    assert.ok('B' in results);
    assert.ok('C' in results);
  });

  test('each result has required fields', async () => {
    const results = await probeArsenal({ S: { type: 'shell' } });
    const r = results.S;
    assert.ok(typeof r.available === 'boolean');
    assert.ok(typeof r.reason === 'string');
    assert.ok(typeof r.probed_at === 'number');
    assert.ok(typeof r.capability === 'string');
  });
});
