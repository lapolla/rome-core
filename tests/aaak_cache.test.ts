import { test, describe, before, after, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import os from 'os';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

/* Mock global.fetch to intercept Ollama embedding calls */
const originalFetch = global.fetch;

function createDeterministicVector(text: string): number[] {
  let baseText = text;
  
  /* Make 'similar prompt' generate a vector very close to 'base prompt' */
  if (text.includes('similar prompt')) {
    baseText = text.replace('similar prompt', 'base prompt');
  }

  const hash = crypto.createHash('sha256').update(baseText).digest();
  const vector = new Array(768).fill(0);
  let magSq = 0;
  for (let i = 0; i < 32; i++) {
    vector[i] = (hash[i] / 127.5) - 1.0;
  }
  
  if (text.includes('similar prompt')) {
    vector[0] += 0.01;
  }

  for (let i = 0; i < 32; i++) {
    magSq += vector[i] * vector[i];
  }

  const mag = Math.sqrt(magSq);
  for (let i = 0; i < 32; i++) {
    vector[i] /= mag;
  }
  return vector;
}

global.fetch = async (url: string | URL | Request, options?: any) => {
  if (url.toString().includes('api/embeddings')) {
    const body = JSON.parse(options.body);
    const vector = createDeterministicVector(body.prompt);
    return new Response(JSON.stringify({ embedding: vector }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  return originalFetch(url, options);
};

import { SemanticCache } from '../src/aaak/cache.js';

describe('SemanticCache', () => {
  let tmpDir: string;

  beforeEach(() => {
    const rand = crypto.randomBytes(8).toString('hex');
    tmpDir = path.join(os.tmpdir(), `aaak-cache-test-${rand}`);
    fs.mkdirSync(tmpDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(tmpDir)) {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  after(() => {
    global.fetch = originalFetch;
  });

  test('init creates the LocalIndex on first call, idempotent on second call', async () => {
    const cache = new SemanticCache(tmpDir);
    await cache.init();
    assert.ok(fs.existsSync(path.join(tmpDir, 'manifests', 'index.json')));
    
    await assert.doesNotReject(async () => {
      await cache.init();
    });
  });

  test('set then get with same capability+prompt returns the cached manifest', async () => {
    const cache = new SemanticCache(tmpDir);
    const manifest = { task_id: 't1', status: 'SUCCESS' };
    await cache.set('CAP1', 'base prompt', manifest as any);
    
    const result = await cache.get('CAP1', 'base prompt');
    assert.ok(result);
    assert.strictEqual(result.task_id, 't1');
    assert.strictEqual(result.status, 'SUCCESS');
  });

  test('get returns null when no match', async () => {
    const cache = new SemanticCache(tmpDir);
    const result = await cache.get('CAP1', 'nonexistent prompt');
    assert.strictEqual(result, null);
  });

  test('get with semantically similar prompt returns cached entry', async () => {
    const cache = new SemanticCache(tmpDir);
    const manifest = { task_id: 't2', status: 'SUCCESS' };
    await cache.set('CAP1', 'base prompt', manifest as any);
    
    const result = await cache.get('CAP1', 'similar prompt');
    assert.ok(result);
    assert.strictEqual(result.task_id, 't2');
  });

  test('get with unrelated prompt returns null', async () => {
    const cache = new SemanticCache(tmpDir);
    const manifest = { task_id: 't3', status: 'SUCCESS' };
    await cache.set('CAP1', 'base prompt', manifest as any);
    
    const result = await cache.get('CAP1', 'completely unrelated text');
    assert.strictEqual(result, null);
  });

  test('Cache isolation: set under capability A, get under capability B returns null', async () => {
    const cache = new SemanticCache(tmpDir);
    const manifest = { task_id: 't4', status: 'SUCCESS' };
    await cache.set('CAP_A', 'base prompt', manifest as any);
    
    const resultA = await cache.get('CAP_A', 'base prompt');
    assert.ok(resultA);
    
    const resultB = await cache.get('CAP_B', 'base prompt');
    assert.strictEqual(resultB, null);
  });

  test('_cache_hash mismatch invalidates entry', async () => {
    const cache = new SemanticCache(tmpDir);
    
    let currentHash = 'hash-v1';
    (cache as any)._hashEnvironment = () => currentHash;

    const manifest = { task_id: 't5', status: 'SUCCESS' };
    await cache.set('CAP1', 'base prompt', manifest as any);

    const result1 = await cache.get('CAP1', 'base prompt');
    assert.ok(result1);

    currentHash = 'hash-v2';
    
    const result2 = await cache.get('CAP1', 'base prompt');
    assert.strictEqual(result2, null);
  });
});
