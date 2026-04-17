// ROME Arsenal Probe
// Checks which declared capabilities are actually usable on the host.
// Result is advisory: daemon still accepts dispatches for "unavailable" caps
// (they'll fail at runtime), but ROME-start.sh and the dashboard
// consume this (via the `probe_arsenal` WS command and `system_status`
// broadcast) to skip spawns and surface misconfiguration clearly.

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as http from 'http';
import * as https from 'https';

export interface ProbeResult {
  capability: string;
  available: boolean;
  reason: string;
  binary?: string;
  probed_at: number;
}

export async function probeArsenal(
  arsenal: Record<string, any>,
): Promise<Record<string, ProbeResult>> {
  const entries = Object.entries(arsenal);
  const results = await Promise.all(
    entries.map(([name, cap]) => probeCapability(name, cap)),
  );
  const out: Record<string, ProbeResult> = {};
  for (const r of results) out[r.capability] = r;
  return out;
}

async function probeCapability(name: string, cap: any): Promise<ProbeResult> {
  const probed_at = Date.now() / 1000;

  // In-process capabilities (SAFE_SHELL, NATIVE_SHELL, TEST) — always usable.
  if (cap?.type !== 'llm') {
    return { capability: name, available: true, reason: 'in-process', probed_at };
  }

  const args: unknown[] = Array.isArray(cap.args) ? cap.args : [];
  const binary = extractBinary(args);
  if (!binary) {
    return { capability: name, available: false, reason: 'no binary in args', probed_at };
  }

  // Resolve: absolute/relative path on disk, or command on PATH.
  const resolved = resolveBinary(binary);
  if (!resolved) {
    return {
      capability: name,
      available: false,
      reason: `binary not found: ${binary}`,
      binary,
      probed_at,
    };
  }

  // Env-gated backends (ollama for GEMMA, etc.) — ping base URL if declared.
  const envPairs = extractEnvPairs(args);
  const baseUrl = envPairs['ANTHROPIC_BASE_URL'];
  if (baseUrl && /^https?:\/\//.test(baseUrl)) {
    const ok = await pingUrl(baseUrl);
    if (!ok) {
      return {
        capability: name,
        available: false,
        reason: `backend unreachable: ${baseUrl}`,
        binary: resolved,
        probed_at,
      };
    }
  }

  return { capability: name, available: true, reason: 'ok', binary: resolved, probed_at };
}

/**
 * First "real" command arg — skips env: prefixes and flags. Returns the
 * placeholder unchanged ({GEMINI_CLI}); caller resolves placeholders.
 */
function extractBinary(args: unknown[]): string | null {
  for (const raw of args) {
    if (typeof raw !== 'string') continue;
    if (raw.startsWith('env:')) continue;
    if (raw.startsWith('-')) continue;
    return raw;
  }
  return null;
}

function extractEnvPairs(args: unknown[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of args) {
    if (typeof raw !== 'string') continue;
    if (!raw.startsWith('env:')) continue;
    const body = raw.slice(4);
    const eq = body.indexOf('=');
    if (eq < 0) continue;
    out[body.slice(0, eq)] = body.slice(eq + 1);
  }
  return out;
}

/**
 * Resolve a binary reference — handles {PLACEHOLDER}, absolute paths, and
 * bare command names (looked up on PATH).
 */
function resolveBinary(ref: string): string | null {
  // Placeholder: {GEMINI_CLI} → env var or guessed path
  if (ref.startsWith('{') && ref.endsWith('}')) {
    const key = ref.slice(1, -1);
    const envVal = process.env[key];
    if (envVal && fs.existsSync(envVal)) return envVal;
    // Heuristic fallback: GEMINI_CLI → ~/projects/gemini-cli/bundle/gemini.js
    const home = process.env.HOME || '';
    const guesses = [
      `${home}/projects/gemini-cli/bundle/gemini.js`,
      `${home}/projects/${key.toLowerCase().replace(/_cli$/, '-cli')}/bundle/${key.toLowerCase().replace(/_cli$/, '')}.js`,
    ];
    for (const g of guesses) if (fs.existsSync(g)) return g;
    return null;
  }

  // Absolute or relative path
  if (ref.includes('/')) {
    return fs.existsSync(ref) ? ref : null;
  }

  // PATH lookup
  try {
    const found = execSync(`command -v ${shellEscape(ref)}`, {
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf-8',
    }).trim();
    return found || null;
  } catch {
    return null;
  }
}

function shellEscape(s: string): string {
  return `'${s.replace(/'/g, `'\\''`)}'`;
}

function pingUrl(url: string, timeoutMs = 1500): Promise<boolean> {
  return new Promise(resolve => {
    try {
      const mod = url.startsWith('https') ? https : http;
      const req = mod.get(url, res => {
        resolve(true);
        res.resume();
        req.destroy();
      });
      req.setTimeout(timeoutMs, () => {
        resolve(false);
        req.destroy();
      });
      req.on('error', () => resolve(false));
    } catch {
      resolve(false);
    }
  });
}

/**
 * CLI entry: `node dist/src/arsenal_probe.js <root>` — prints JSON probe result.
 * Used by ROME-start.sh to gate worker spawns before the daemon starts.
 */
if (import.meta.url === `file://${process.argv[1]}`) {
  const root = process.argv[2] || process.cwd();
  const arsenalPath = `${root}/arsenal/core_arsenal.json`;
  try {
    const raw = fs.readFileSync(arsenalPath, 'utf-8');
    const parsed = JSON.parse(raw);
    probeArsenal(parsed.capabilities || {}).then(results => {
      process.stdout.write(JSON.stringify(results, null, 2) + '\n');
      process.exit(0);
    });
  } catch (e) {
    process.stderr.write(`probe failed: ${(e as Error).message}\n`);
    process.exit(1);
  }
}
