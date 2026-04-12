import { test, describe } from 'node:test';
import assert from 'node:assert';
import { parseUsage, calcGeminiCost } from '../src/legion_worker.js';

describe('legion_worker parser', () => {
  test('should parse Gemini usage correctly', () => {
    const raw = `Some text here...
{
  "response": "Hello!",
  "stats": {
    "models": {
      "gemini-1.5-flash": {
        "tokens": { "input": 100, "candidates": 50, "total": 150 }
      }
    }
  }
}`;
    const [text, usage] = parseUsage(raw);
    assert.strictEqual(text, "Hello!");
    assert.strictEqual(usage?.model, "gemini-1.5-flash");
    assert.strictEqual(usage?.total_tokens, 150);
    assert.ok(usage?.cost_usd! > 0);
  });

  test('should parse Claude usage even with trailing warnings', () => {
    const raw = `{
  "result": "Clean result",
  "usage": { "input_tokens": 10, "output_tokens": 5 },
  "total_cost_usd": 0.001
}
Warning: some noise at the end`;
    const [text, usage] = parseUsage(raw);
    assert.strictEqual(text, "Clean result");
    assert.strictEqual(usage?.input_tokens, 10);
    assert.strictEqual(usage?.cost_usd, 0.001);
  });

  test('should handle robust JSON extraction with nested braces', () => {
    const raw = `Noise... {"result": "Extracted", "usage": {"in": 1}} ...Noise`;
    const [text, usage] = parseUsage(raw);
    assert.strictEqual(text, "Extracted");
    assert.ok(usage !== null);
  });
});

describe('legion_worker cost calculator', () => {
  test('should calculate correct cost for gemini-1.5-flash', () => {
    const cost = calcGeminiCost('gemini-1.5-flash', 1000000, 1000000);
    // Pricing: [0.075, 0.30] per 1M tokens
    assert.strictEqual(cost, 0.075 + 0.30);
  });

  test('should calculate correct cost for gemma4 local', () => {
    const cost = calcGeminiCost('gemma4:e4b', 1000, 1000);
    // Pricing: [3.00, 15.00] per 1M tokens -> 0.003 + 0.015 = 0.018 for 1k
    assert.strictEqual(cost, 0.018);
  });
});
