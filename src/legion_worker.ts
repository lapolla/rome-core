#!/usr/bin/env node
/**
 * ROME LEGIONARY V6: PERSISTENT WORKER ENGINE (TypeScript)
 */

import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import { WebSocket, WebSocketServer } from 'ws';

// ── constants ──────────────────────────────────────────────────────────────────

const ROME_ROOT = process.env.ROME_ROOT ?? path.resolve(process.cwd(), '..');
const MAX_ARTIFACT_SIZE = 5 * 1024 * 1024;

// ── types ──────────────────────────────────────────────────────────────────────

interface Usage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
}

interface PendingSignal {
  type: 'dispatch' | 'await' | 'read' | 'shell';
  capability?: string;
  prompt?: string;
  task_id?: string;
  path?: string;
  command?: string;
}

interface RomeSignals {
  primary_artifact: string | null;
  metadata: Record<string, string>;
  status_override: string | null;
  pending: PendingSignal[];
}

interface Manifest {
  rome_v: string;
  task_id: string;
  status: string;
  metadata: Record<string, string>;
  usage: Usage | null;
  report: string;
  progress: { count: number; final: string | null; log_path: string };
  runtime: { elapsed_s: number; exit_code: number };
  artifacts: Array<{ path: string; type: string }>;
}

// ── UI & PROGRESS ──────────────────────────────────────────────────────────────

export class LegionaryUI {
  private taskId: string;
  private barWidth = 30;
  private t0: number;
  percent = 0;
  private hbChars = ['+', 'x', '*', '.', 'o'];
  private hbIdx = 0;
  progressLines: string[] = [];
  private wsSender?: (ev: object) => Promise<void>;
  private progressStream: fs.WriteStream | null = null;
  private silent: boolean;

  constructor(
    taskId: string,
    t0: number,
    wsSender?: (ev: object) => Promise<void>,
    taskDir?: string,
  ) {
    this.taskId = taskId;
    this.t0 = t0;
    this.wsSender = wsSender;
    const dir = taskDir ?? process.env.ROME_TASK_DIR ?? '.';
    const progressPath = path.join(dir, 'progress.log');
    try {
      this.progressStream = fs.createWriteStream(progressPath, { flags: 'w' });
    } catch {
      this.progressStream = null;
    }
    const silentRaw = (process.env.ROME_SILENT ?? '').trim().toLowerCase();
    this.silent = ['1', 'true', 'yes'].includes(silentRaw);
  }

  log(percent: number, msg: string): void {
    this.percent = percent;
    const elapsed = Date.now() / 1000 - this.t0;
    const filled = Math.floor(this.barWidth * this.percent / 100);
    const bar = '\u2588'.repeat(filled) + '\u2591'.repeat(this.barWidth - filled);
    const displayId = this.taskId.includes('_')
      ? (this.taskId.split('_').at(-1) ?? this.taskId)
      : this.taskId;
    const vis =
      `\r\x1b[K[ROME:${displayId.padEnd(14)}] ${bar}` +
      `  ${String(this.percent).padStart(3)}% [${elapsed.toFixed(1).padStart(5)}s] >> ${msg.slice(0, 30)}`;
    if (!this.silent) {
      process.stderr.write(vis);
    }
    const hb = this.hbChars[this.hbIdx % this.hbChars.length];
    this.hbIdx++;
    const line = `${this.percent}% ${hb} [${elapsed.toFixed(1)}s] ${msg.slice(0, 40)}`;
    this.progressLines.push(line);
    if (this.progressStream) {
      try { this.progressStream.write(line + '\n'); } catch { /* ignore */ }
    }
    if (this.wsSender) {
      void this.wsSender({
        type: 'event',
        event: {
          type: 'progress',
          task_id: this.taskId,
          payload: { percent: this.percent, message: msg },
        },
      });
    }
  }

  finalize(status: string): void {
    const elapsed = Date.now() / 1000 - this.t0;
    const color = status === 'SUCCESS' ? '\x1b[92m' : '\x1b[91m';
    const bar = '\u2588'.repeat(this.barWidth);
    const displayId = this.taskId.includes('_')
      ? (this.taskId.split('_').at(-1) ?? this.taskId)
      : this.taskId;
    const vis =
      `\r\x1b[K[ROME:${displayId.padEnd(14)}] ${color}${bar}` +
      `  [${status.padEnd(7)}] [${elapsed.toFixed(1).padStart(5)}s]\x1b[0m >> Mission complete.`;
    if (!this.silent) {
      process.stderr.write(vis + '\n');
    }
  }

  close(): void {
    if (this.progressStream) {
      try { this.progressStream.end(); } catch { /* ignore */ }
    }
  }

  handleBytes(buf: Buffer): void {
    try {
      const text = buf.toString('utf8');
      const textLower = text.toLowerCase();

      if (
        textLower.includes('"toolcall"') ||
        textLower.includes('"tool_use"') ||
        textLower.includes('"function_call"')
      ) {
        const match = text.match(/"name"\s*:\s*"(\w+)"/);
        if (match) {
          this.log(Math.min(90, this.percent + 5), `Calling ${match[1]}...`);
          return;
        }
      }

      const stepMatch = textLower.match(/(?:step\s+)?(\d+)\s*\/\s*(\d+)/);
      if (stepMatch) {
        const cur = parseInt(stepMatch[1], 10);
        const total = parseInt(stepMatch[2], 10);
        if (total > 0) {
          this.log(Math.min(95, Math.floor(cur / total * 95)), `Step ${cur}/${total}`);
          return;
        }
      }

      const pctMatch = text.match(/(\d{1,3})%/);
      if (pctMatch) {
        const pct = parseInt(pctMatch[1], 10);
        if (pct > 0 && pct <= 100) {
          this.log(Math.min(95, pct), `Progress ${pct}%`);
          return;
        }
      }

      const KEYWORDS: Array<[string, number, string]> = [
        ['reading',    25, 'Reading files...'],
        ['searching',  30, 'Searching...'],
        ['thinking',   20, 'Reasoning...'],
        ['planning',   25, 'Planning...'],
        ['analyzing',  50, 'Analyzing...'],
        ['compiling',  60, 'Compiling...'],
        ['building',   60, 'Building...'],
        ['testing',    70, 'Running tests...'],
        ['writing',    75, 'Writing...'],
        ['editing',    75, 'Editing...'],
        ['creating',   70, 'Creating...'],
        ['generating', 80, 'Generating...'],
        ['formatting', 85, 'Formatting...'],
      ];
      for (const [kw, targetPct, msg] of KEYWORDS) {
        if (textLower.includes(kw)) {
          this.log(Math.max(this.percent, Math.min(95, targetPct)), msg);
          return;
        }
      }

      if (this.percent < 95) {
        this.log(Math.min(95, this.percent + 1), 'Working...');
      }
    } catch { /* ignore */ }
  }
}

// ── PRICING ────────────────────────────────────────────────────────────────────

const _GEMINI_PRICING: Record<string, [number, number]> = {
  'gemini-3.1-pro':        [2.00,  12.00],
  'gemini-3-pro':          [2.00,  12.00],
  'gemini-3-flash':        [0.50,   3.00],
  'gemini-2.5-pro':        [1.25,  10.00],
  'gemini-2.5-flash-lite': [0.10,   0.40],
  'gemini-2.5-flash':      [0.30,   2.50],
  'gemini-2.0-flash-lite': [0.075,  0.30],
  'gemini-2.0-flash':      [0.10,   0.40],
  'gemini-1.5-pro':        [1.25,   5.00],
  'gemini-1.5-flash':      [0.075,  0.30],
  'gemma4':                [3.00,  15.00], // 0.003/0.015 per 1k (standard local estimate)
};

const _RATE_LIMIT_SIGNALS = [
  '429',
  'rate_limit',
  'rateLimitExceeded',
  'MODEL_CAPACITY_EXHAUSTED',
  'No capacity available',
  'RESOURCE_EXHAUSTED',
];

export function isRateLimitError(text: string): boolean {
  return _RATE_LIMIT_SIGNALS.some(s => text.includes(s));
}

export function calcGeminiCost(
  model: string,
  inputTokens: number,
  outputTokens: number,
): number | null {
  const modelLower = model.toLowerCase();
  for (const [key, [inpRate, outRate]] of Object.entries(_GEMINI_PRICING)) {
    if (modelLower.includes(key)) {
      return (
        Math.round(
          ((inputTokens / 1_000_000) * inpRate +
            (outputTokens / 1_000_000) * outRate) *
            1e6,
        ) / 1e6
      );
    }
  }
  return null;
}

function loadModelChain(capabilityName: string): string[] {
  try {
    const arsenalPath = path.join(ROME_ROOT, 'arsenal', 'core_arsenal.json');
    const arsenal = JSON.parse(fs.readFileSync(arsenalPath, 'utf-8')) as {
      capabilities?: Record<string, { model?: string; model_fallback_chain?: string[] }>;
    };
    const cap = arsenal.capabilities?.[capabilityName] ?? {};
    const primary = cap.model;
    const fallback = cap.model_fallback_chain ?? [];
    if (primary) return [primary, ...fallback];
  } catch { /* ignore */ }
  return [];
}

// ── PARSING ────────────────────────────────────────────────────────────────────

function extractJson(text: string): Record<string, any> | null {
  try {
    const start = text.indexOf('{');
    if (start < 0) return null;
    
    let depth = 0;
    let end = -1;
    for (let i = start; i < text.length; i++) {
      if (text[i] === '{') depth++;
      else if (text[i] === '}') {
        depth--;
        if (depth === 0) {
          end = i;
          break;
        }
      }
    }
    
    if (end > 0) {
      return JSON.parse(text.slice(start, end + 1));
    }
  } catch (e) {}
  return null;
}

export function parseUsage(text: string): [string, Usage | null] {
  if (!text) return [text, null];
  
  const data = extractJson(text);
  if (!data) return [text, null];
  
  let cleanText = text;
  const startIdx = text.indexOf('{');
  if (startIdx >= 0) {
    cleanText = text.slice(0, startIdx).trim();
  }

  // Claude shape: { result, usage, modelUsage?, total_cost_usd? }
  if ('result' in data && 'usage' in data) {
    const u = (data.usage ?? {}) as Record<string, number>;
    let model = 'unknown';
    const mu = data.modelUsage;
    if (mu && typeof mu === 'object' && !Array.isArray(mu)) {
      model = Object.keys(mu as object)[0] ?? 'unknown';
    }
    const usage: Usage = {
      model,
      input_tokens:  (u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0),
      output_tokens: u.output_tokens ?? 0,
      total_tokens:
        (u.input_tokens ?? 0) +
        (u.cache_read_input_tokens ?? 0) +
        (u.cache_creation_input_tokens ?? 0) +
        (u.output_tokens ?? 0),
      cost_usd: typeof data.total_cost_usd === 'number' ? data.total_cost_usd : null,
    };
    return [String(data.result ?? cleanText), usage];
  }

  // Gemini shape: { response, stats: { models: { <name>: { tokens: { input, candidates, total } } } } }
  if ('response' in data && 'stats' in data) {
    const stats = (data.stats ?? {}) as Record<string, unknown>;
    const models = (stats.models ?? {}) as Record<string, Record<string, unknown>>;
    let totalIn = 0, totalOut = 0, totalAll = 0, modelName = 'unknown';
    for (const [name, info] of Object.entries(models)) {
      modelName = name;
      const tokens = (info.tokens ?? {}) as Record<string, number>;
      totalIn  += tokens.input      ?? 0;
      totalOut += tokens.candidates ?? 0;
      totalAll += tokens.total      ?? 0;
    }
    const usage: Usage = {
      model: modelName,
      input_tokens:  totalIn,
      output_tokens: totalOut,
      total_tokens:  totalAll,
      cost_usd: calcGeminiCost(modelName, totalIn, totalOut),
    };
    return [String(data.response ?? cleanText), usage];
  }

  return [text, null];
}

export function parseRomeSignals(text: string): RomeSignals {
  const signals: RomeSignals = {
    primary_artifact: null,
    metadata: {},
    status_override: null,
    pending: [],
  };
  if (!text) return signals;

  try {
    const artifactMatch = text.match(/\[ROME_START\]([\s\S]*?)\[ROME_END\]/);
    if (artifactMatch) {
      let artifact = artifactMatch[1].trim();
      if (artifact.length > MAX_ARTIFACT_SIZE) {
        artifact = artifact.slice(0, MAX_ARTIFACT_SIZE);
        signals.metadata.truncated = 'true';
      }
      signals.primary_artifact = artifact;
    }
  } catch { /* ignore */ }

  try {
    const metaRe = /\[ROME_META:\s*(\w+)\s*=\s*(.*?)\]/g;
    let m: RegExpExecArray | null;
    while ((m = metaRe.exec(text)) !== null) {
      signals.metadata[m[1]] = m[2].trim();
    }
  } catch { /* ignore */ }

  try {
    const statusMatch = text.match(/\[ROME_STATUS:\s*(SUCCESS|FAILED|RETRY)\]/i);
    if (statusMatch) signals.status_override = statusMatch[1].toUpperCase();
  } catch { /* ignore */ }

  // ROME V6: Direct Agent signals
  const dispatchRe = /\[ROME_DISPATCH:\s*(\w+)\s+"(.*?)"\]/g;
  let dm: RegExpExecArray | null;
  while ((dm = dispatchRe.exec(text)) !== null) {
    signals.pending.push({ type: 'dispatch', capability: dm[1], prompt: dm[2] });
  }

  const awaitRe = /\[ROME_AWAIT:\s*(.*?)\]/g;
  let am: RegExpExecArray | null;
  while ((am = awaitRe.exec(text)) !== null) {
    signals.pending.push({ type: 'await', task_id: am[1].trim() });
  }

  const readRe = /\[ROME_READ:\s*(.*?)\]/g;
  let rm: RegExpExecArray | null;
  while ((rm = readRe.exec(text)) !== null) {
    signals.pending.push({ type: 'read', path: rm[1].trim() });
  }

  const shellRe = /\[ROME_SHELL:\s*"(.*?)"\]/g;
  let sm: RegExpExecArray | null;
  while ((sm = shellRe.exec(text)) !== null) {
    signals.pending.push({ type: 'shell', command: sm[1] });
  }

  return signals;
}

function isEmptyContent(content: string | null | undefined): boolean {
  if (!content) return true;
  const cleaned = content.replace(/`/g, '').trim();
  if (cleaned.length === 0) return true;
  if (/^(OK|ERR):[a-zA-Z0-9_-]+$/.test(cleaned)) return true;
  return false;
}

export type SignalHandler = (signal: PendingSignal) => Promise<object>;

// ── ROME SIGNAL HANDLER ────────────────────────────────────────────────────────

async function handleRomeSignal(signal: PendingSignal, handler?: SignalHandler): Promise<object> {
  if (signal.type === 'read' && signal.path) {
    try {
      return { ok: true, content: fs.readFileSync(signal.path, 'utf-8') };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }
  
  if (handler) {
    try {
      return await handler(signal);
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  return { ok: false, error: `Signal type '${signal.type}' not yet wired in TS worker` };
}

// ── TASK EXECUTION ─────────────────────────────────────────────────────────────

export async function executeTask(
  taskId: string,
  capabilityName: string,
  cmdArgs: string[],
  wsSender?: (ev: object) => Promise<void>,
  modelChain?: string[],
  signalHandler?: SignalHandler,
): Promise<Manifest> {
  const t0 = Date.now() / 1000;
  const cmdArgsOrig = cmdArgs;

  if (modelChain === undefined && cmdArgs.includes('{MODEL}')) {
    modelChain = loadModelChain(capabilityName);
  }
  if (modelChain && modelChain.length > 0 && cmdArgs.includes('{MODEL}')) {
    cmdArgs = cmdArgs.map(a => (a === '{MODEL}' ? modelChain![0] : a));
  }

  const taskDir = path.join(ROME_ROOT, 'legions', taskId);
  fs.mkdirSync(taskDir, { recursive: true });

  const taskMdPath = path.join(taskDir, 'task.md');
  let initialTaskContent = '';
  if (fs.existsSync(taskMdPath)) {
    try { initialTaskContent = fs.readFileSync(taskMdPath, 'utf-8'); } catch { /* ignore */ }
  }

  const ui = new LegionaryUI(taskId, t0, wsSender, taskDir);
  ui.log(0, 'Engaged.');

  // Separate env:KEY=VAL args from real command args
  const filteredArgs = cmdArgs.filter(a => !a.startsWith('env:'));
  const envOverrides: NodeJS.ProcessEnv = {};
  for (const a of cmdArgs) {
    if (a.startsWith('env:')) {
      const rest = a.slice(4);
      const eq = rest.indexOf('=');
      if (eq >= 0) envOverrides[rest.slice(0, eq)] = rest.slice(eq + 1);
    }
  }

  const combinedEnv: NodeJS.ProcessEnv = {
    ...process.env,
    ...envOverrides,
    PYTHONUNBUFFERED: '1',
    ROME_TASK_ID: taskId,
    ROME_TASK_DIR: taskDir,
    ROME_TASK_TOKEN: process.env.ROME_TASK_TOKEN ?? '',
  };

  const child = spawn(filteredArgs[0], filteredArgs.slice(1), {
    detached: true,
    cwd: taskDir,
    env: combinedEnv,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  const stdoutLines: Buffer[] = [];
  const stderrChunks: Buffer[] = [];

  child.stderr?.on('data', (data: Buffer) => { stderrChunks.push(data); });

  const exitPromise = new Promise<number>(resolve => {
    child.on('exit', code => resolve(code ?? 0));
    child.on('error', () => resolve(1));
  });

  // Stream stdout line-by-line; await signal responses before continuing
  const rl = readline.createInterface({ input: child.stdout!, crlfDelay: Infinity });
  for await (const line of rl) {
    const buf = Buffer.from(line + '\n');
    ui.handleBytes(buf);
    stdoutLines.push(buf);

    if (line.includes('[ROME_')) {
      const sigData = parseRomeSignals(line);
      for (const pending of sigData.pending) {
        try {
          const res = await handleRomeSignal(pending, signalHandler);
          child.stdin?.write(JSON.stringify(res) + '\n');
        } catch (e) {
          child.stdin?.write(JSON.stringify({ ok: false, error: String(e) }) + '\n');
        }
      }
    }
  }

  const exitCode = await exitPromise;
  let status = exitCode === 0 ? 'SUCCESS' : 'FAILED';
  ui.finalize(status);
  ui.close();

  const rawText = Buffer.concat([...stdoutLines, ...stderrChunks]).toString('utf8');
  const [finalText, usage] = parseUsage(rawText);
  const signals = parseRomeSignals(finalText);
  const artifactPath = path.join(taskDir, `report_${taskId}.txt`);
  let reportContent = signals.primary_artifact ?? finalText;

  // Recovery: check if task.md was extended with content by the subprocess
  if (isEmptyContent(reportContent) && fs.existsSync(taskMdPath)) {
    try {
      const currentTaskContent = fs.readFileSync(taskMdPath, 'utf-8');
      let recovered: string | null = null;
      if (currentTaskContent.length > initialTaskContent.length) {
        recovered = currentTaskContent.slice(initialTaskContent.length).trim();
      }
      if (isEmptyContent(recovered)) {
        const taskSignals = parseRomeSignals(currentTaskContent);
        recovered =
          taskSignals.primary_artifact ??
          (currentTaskContent.trim().length > 100 ? currentTaskContent.trim() : null);
      }
      if (recovered) {
        reportContent = recovered;
        signals.metadata.recovered_from_task_md = 'true';
      }
    } catch { /* ignore */ }
  }

//   fs.writeFileSync(artifactPath, reportContent, 'utf-8');

  if (signals.status_override) status = signals.status_override;
  if (isEmptyContent(reportContent) && status === 'SUCCESS') {
    status = 'FAILED';
    signals.metadata.failure_reason = 'empty_report';
  }

  // Model fallback: retry with next model on rate-limit errors
  if (status === 'FAILED' && modelChain && modelChain.length > 1 && isRateLimitError(rawText)) {
    console.log(`[MODEL FALLBACK] ${modelChain[0]} → ${modelChain[1]}`);
    return executeTask(taskId, capabilityName, cmdArgsOrig, wsSender, modelChain.slice(1));
  }

  const progressLogPath = path.join(taskDir, 'progress.log');
  const manifest: Manifest = {
    rome_v: '6.0.0',
    task_id: taskId,
    status,
    metadata: signals.metadata,
    usage,
    report: reportContent,
    progress: {
      count: ui.progressLines.length,
      final: ui.progressLines.at(-1) ?? null,
      log_path: progressLogPath,
    },
    runtime: { elapsed_s: Date.now() / 1000 - t0, exit_code: exitCode },
    artifacts: [{ path: artifactPath, type: signals.primary_artifact ? 'extracted' : 'raw' }],
  };
  fs.writeFileSync(
    path.join(taskDir, 'manifest.json'),
    JSON.stringify(manifest, null, 2),
    'utf-8',
  );

  return manifest;
}

// ── PEER SERVER ────────────────────────────────────────────────────────────────

async function startPeerServer(
  capabilities: string[],
  capabilityCmdBase: string[],
): Promise<{ port: number; close: () => void }> {
  const wss = new WebSocketServer({ host: '127.0.0.1', port: 0 });

  const port = await new Promise<number>((resolve, reject) => {
    wss.on('listening', () => {
      const addr = wss.address();
      resolve(typeof addr === 'object' && addr !== null ? addr.port : 0);
    });
    wss.on('error', reject);
  });

  wss.on('connection', (ws) => {
    ws.on('message', (raw) => {
      void (async () => {
        try {
          const msg = JSON.parse(raw.toString()) as Record<string, unknown>;
          if (msg.type !== 'command') return;
          const command = String(msg.command ?? '');
          const payload = (msg.payload ?? {}) as Record<string, unknown>;
          const requestId = String(msg.request_id ?? '');

          if (command === 'ping') {
            ws.send(JSON.stringify({ type: 'response', request_id: requestId, ok: true }));
            return;
          }

          if (command === 'dispatch') {
            const taskId = String(payload.task_id ?? '');
            const cap = String(payload.capability ?? capabilities[0] ?? '');
            const prompt = payload.prompt != null ? String(payload.prompt) : undefined;

            ws.send(JSON.stringify({
              type: 'response', request_id: requestId,
              ok: true, payload: { task_id: taskId, accepted: true },
            }));

            const cmd = [...capabilityCmdBase];
            // If the prompt contains ROME metadata (GOAL/INTENT), strip it for shell workers
            let cleanPrompt = prompt || '';
            if (cleanPrompt.includes('GOAL:')) {
              const taskIdx = cleanPrompt.indexOf('TASK:');
              if (taskIdx >= 0) {
                cleanPrompt = cleanPrompt.slice(taskIdx + 5).trim();
              }
            }
            if (cleanPrompt) cmd.push(cleanPrompt);

            void (async () => {
              const noopSender = async (_ev: object): Promise<void> => { /* no-op */ };
              const manifest = await executeTask(taskId, cap, cmd, noopSender);
              let reportContent = '';
              try {
                const p = manifest.artifacts[0]?.path;
                if (p) reportContent = fs.readFileSync(p, 'utf-8');
              } catch { /* ignore */ }
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                  type: 'event',
                  event: {
                    type: 'complete', task_id: taskId,
                    payload: { status: manifest.status, usage: manifest.usage, report: reportContent },
                  },
                }));
              }
            })();
          }
        } catch (e) {
          console.error('ROME A2A: peer handler error:', e);
        }
      })();
    });
  });

  console.log(`ROME A2A: Peer server listening on ws://127.0.0.1:${port}`);
  return { port, close: () => wss.close() };
}

// ── WORKER LOOP ────────────────────────────────────────────────────────────────

export async function runWorker(
  wsUrl: string,
  capabilities: string[],
  capabilityCmdBase: string[],
  token?: string,
): Promise<void> {
  const urlWithToken = token ? `${wsUrl}${wsUrl.includes('?') ? '&' : '?'}token=${token}` : wsUrl;
  console.log(`ROME V6: Connecting as persistent worker to ${wsUrl}`);

  const { port: peerPort } = await startPeerServer(capabilities, capabilityCmdBase);
  const peerUrl = `ws://127.0.0.1:${peerPort}`;

  let backoff = 1.0;
  while (true) {
    await new Promise<void>(resolveLoop => {
      const ws = new WebSocket(urlWithToken);

      ws.on('open', () => {
        backoff = 1.0;
        console.log('ROME V6: Registered. Awaiting tasks...');
        ws.send(JSON.stringify({
          type: 'agent_hello',
          payload: {
            capabilities,
            version: '6.0.0',
            platform: process.platform,
            peer_url: peerUrl,
          }
        }));
      });

      ws.on('message', (raw) => {
        void (async () => {
          try {
            const msg = JSON.parse(raw.toString()) as Record<string, unknown>;
            console.log(`ROME V6: Received message type=${String(msg.type ?? '')}`, JSON.stringify(msg));

            if (msg.type === 'worker_ack') {
              console.log('ROME V6: Handshake confirmed by server:', JSON.stringify((msg as any).payload || {}));
              return;
            }

            if (msg.type !== 'command' || msg.command !== 'dispatch') return;

            const payload = (msg.payload ?? {}) as Record<string, unknown>;
            const taskId  = String(payload.task_id  ?? '');
            const cap     = String(payload.capability ?? '');
            const prompt  = payload.prompt != null ? String(payload.prompt) : undefined;

            const cmd = [...capabilityCmdBase];
            // If the prompt contains ROME metadata (GOAL/INTENT), strip it for shell workers
            let cleanPrompt = prompt || '';
            if (cleanPrompt.includes('GOAL:')) {
              const taskIdx = cleanPrompt.indexOf('TASK:');
              if (taskIdx >= 0) {
                cleanPrompt = cleanPrompt.slice(taskIdx + 5).trim();
              }
            }
            if (cleanPrompt) cmd.push(cleanPrompt);

            const uiSender = async (ev: object): Promise<void> => {
              if (ws.readyState === WebSocket.OPEN) {
                try { ws.send(JSON.stringify(ev)); } catch { /* ignore */ }
              }
            };

            void (async () => {
              const manifest = await executeTask(taskId, cap, cmd, uiSender);
              const reportPath = manifest.artifacts[0]?.path;
              // Use manifest.report directly — artifact write may be skipped
              let reportContent = manifest.report || '';
              if (!reportContent && reportPath) {
                try { reportContent = fs.readFileSync(reportPath, 'utf-8'); } catch { /* ignore */ }
              }
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                  type: 'event',
                  event: {
                    type: 'complete', task_id: taskId,
                    payload: {
                      status: manifest.status,
                      usage: manifest.usage,

                      report: reportContent,
                    },
                  },
                }));
              }
            })();

            // Ack dispatch immediately so daemon keeps WS responsive
            ws.send(JSON.stringify({ type: 'response', request_id: msg.request_id, ok: true }));
          } catch (e) {
            console.error('ROME V6: Message handler error:', e);
          }
        })();
      });

      ws.on('error', (err: Error) => {
        console.error(`ROME V6: Worker error: ${err.message}. Reconnecting in ${backoff.toFixed(1)}s...`);
      });

      ws.on('close', () => resolveLoop());
    });

    await new Promise<void>(r => setTimeout(r, backoff * 1000));
    backoff = Math.min(backoff * 2, 30);
  }
}

// ── CLI ENTRY ──────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  let mode: 'once' | 'worker' = 'once';
  let taskId: string | undefined;
  let wsUrl: string | undefined;
  let wsToken: string | undefined;
  const capabilities: string[] = [];
  const unknown: string[] = [];

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--mode')         { mode    = argv[++i] as 'once' | 'worker'; }
    else if (arg === '--task-id') { taskId  = argv[++i]; }
    else if (arg === '--ws-url')  { wsUrl   = argv[++i]; }
    else if (arg === '--ws-token'){ wsToken = argv[++i]; }
    else if (arg === '--capabilities') {
      while (i + 1 < argv.length && !argv[i + 1].startsWith('--')) {
        capabilities.push(argv[++i]);
      }
    } else if (arg === '--') {
      unknown.push(...argv.slice(i + 1));
      break;
    } else {
      unknown.push(arg);
    }
  }

  if (!wsUrl || !wsToken) {
    const configPath = path.join(ROME_ROOT, 'dictator', 'config.json');
    if (fs.existsSync(configPath)) {
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        if (!wsUrl && config.mesh_port) {
          wsUrl = `ws://127.0.0.1:${config.mesh_port}/ws`;
        }
        if (!wsToken && config.sovereign_token_path) {
          const tokenPath = path.join(ROME_ROOT, config.sovereign_token_path);
          if (fs.existsSync(tokenPath)) {
            wsToken = fs.readFileSync(tokenPath, 'utf-8').trim();
          }
        }
      } catch (e) {
        console.error('Error reading config.json:', e);
      }
    }
  }

  if (mode === 'worker') {
    if (capabilities.length === 0) {
      console.error('Worker mode requires --capabilities');
      process.exit(1);
    }
    if (!wsUrl) {
      console.error('Worker mode requires --ws-url or config.json mesh_port');
      process.exit(1);
    }
    const tok = wsToken ?? process.env.ROME_WEBSOCKET_TOKEN;
    const capCmd = unknown.filter(a => a !== '--');
    await runWorker(wsUrl, capabilities, capCmd, tok);
  } else {
    // Legacy once-off mode: <task_id> <start_time> <cmd...>
    const args = process.argv.slice(2);
    if (args.length < 3) { process.exit(1); }
    const tid = args[0];
    const cmd = args.slice(2);
    const manifest = await executeTask(tid, 'LEGACY', cmd);
    console.log(manifest.status === 'SUCCESS' ? 'OK' : 'ERR');
  }

  void taskId; // parsed but unused in once-mode (kept for parity with Python argparse)
}

const entry = process.argv[1] ?? '';
if (entry.endsWith('legion_worker.js') || entry.endsWith('legion_worker.ts')) {
  main().catch(console.error);
}
