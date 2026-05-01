import { WebSocketServer, WebSocket } from 'ws';
import { v4 as uuidv4 } from 'uuid';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';
import { EventEmitter } from 'events'; // Added
import { AAAK } from './aaak/index.js';
import { SemanticCache } from './aaak/cache.js';
import { spawn } from 'child_process';
import type { RomeMessage, TaskUsage, RomeEvent } from './rome_types.js';
import { getRomeVersion } from './rome_types.js';
import { EventBus, TaskRegistry, WorkerRegistry, Blackboard, MeshReducer } from './registry.js';
import { executeTask } from './legion_worker.js';
import { executeShell } from './shell_executor.js';
import { probeArsenal, type ProbeResult } from './arsenal_probe.js';

const ROME_ROOT = process.env.ROME_ROOT || process.cwd();

const QUOTA_PATTERNS = ['QUOTA_EXHAUSTED', 'TerminalQuotaError', 'exhausted your capacity', 'quota will reset'];
function isQuotaError(msg: string): boolean {
  return QUOTA_PATTERNS.some(p => msg.includes(p));
}


function extractStateSignals(report: string): Array<{ key: string; value: any }> {
  const results: Array<{ key: string; value: any }> = [];
  const re = /\[ROME_STATE:\s*(\{[^}]+\})\]/g;
  let m;
  while ((m = re.exec(report)) !== null) {
    try {
      const obj = JSON.parse(m[1]);
      if (obj.key !== undefined && obj.value !== undefined) results.push(obj);
    } catch {}
  }
  return results;
}
const BUSY_PATTERNS = ['installing', 'building', 'compiling', 'searching', 'thinking'];

function loadArsenal(root: string) {
  const arsenalPath = path.join(root, 'arsenal', 'core_arsenal.json');
  let raw: string;
  try {
    raw = fs.readFileSync(arsenalPath, 'utf-8');
  } catch (e) {
    throw new Error(`ROME: arsenal not found at ${arsenalPath}: ${(e as Error).message}`);
  }
  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`ROME: arsenal at ${arsenalPath} is not valid JSON: ${(e as Error).message}`);
  }
  const caps = parsed?.capabilities;
  if (!caps || typeof caps !== 'object' || Object.keys(caps).length === 0) {
    throw new Error(`ROME: arsenal at ${arsenalPath} has no capabilities defined`);
  }
  return caps;
}

export class PeerServer {
  private wss: WebSocketServer | null = null;
  private server: http.Server | null = null;
  private bus = new EventBus();
  private registry = new TaskRegistry();
  private workers = new WorkerRegistry();
  private blackboard = new Blackboard();

  private reducer = new MeshReducer();
  // FIX 3: Change AAAK initialization path
  private aaak: AAAK;
  private semanticCache: SemanticCache;
  private startTime = Date.now() / 1000;
  private activeSubprocesses = new Map<string, { kill: () => void }>();
  private tickScheduled = false;
  private arsenal: any;
  private probeResults: Record<string, ProbeResult> = {};
  private capability: string;
  private port: number;
  private eventReplayWindow: number = 90000;

  // Dashboard stats
  private projectTotalCost: number = 0;
  private projectTotalTokens: number = 0;

  constructor(capability: string, port?: number, aaakFactsPath?: string) {
    this.aaak = new AAAK('default', { enabled: true }, aaakFactsPath ?? path.join(ROME_ROOT, 'legions', '.aaak_facts'));
    this.semanticCache = new SemanticCache(path.join(ROME_ROOT, 'legions', '.aaak_cache'));
    this.capability = capability.toUpperCase();
    this.arsenal = loadArsenal(ROME_ROOT);
    this.registry.hydrateFromLog(path.join(ROME_ROOT, 'logs', 'rome.jsonl'));
    this.blackboard.setPersistence(path.join(ROME_ROOT, 'legions', '.rome_STATE.json'));

    let meshPort = 8741;

    try {
      const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
      if (fs.existsSync(configPath)) {
        const content = fs.readFileSync(configPath, 'utf-8');
        for (const line of content.split('\n')) {
          if (line.startsWith('MESH_PORT=')) meshPort = parseInt(line.split('=')[1]);
          if (line.startsWith('EVENT_REPLAY_WINDOW=')) this.eventReplayWindow = parseInt(line.split('=')[1]);
        }
      }
      const jsonPath = path.join(ROME_ROOT, 'dictator', 'config.json');
      if (fs.existsSync(jsonPath)) {
        const jsonConfig = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
        if (jsonConfig.eventReplayWindow !== undefined) {
          this.eventReplayWindow = jsonConfig.eventReplayWindow;
        }
      }
    } catch {}

    this.port = port !== undefined ? port : meshPort;

    // Initialize project totals by aggregating logs on startup
    this.loadProjectTotals().catch((e) => {
      console.error(`ROME: Failed to initialize project totals:`, e);
    });
  }


  async start(): Promise<number> {
    // Probe the arsenal for binary/backend availability. Advisory only —
    // dispatches still work for anything the probe flags; this surfaces
    // misconfiguration early and gates ROME-start.sh worker spawns.
    this.probeResults = await probeArsenal(this.arsenal);

    this.server = http.createServer((req, res) => {
      const url = new URL(req.url || '', `http://${req.headers.host}`);
      if (url.pathname === '/dashboard' || url.pathname === '/dashboard/') {
        const indexPath = path.join(ROME_ROOT, 'dashboard', 'index.html');
        if (fs.existsSync(indexPath)) {
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end(fs.readFileSync(indexPath));
          return;
        }
      }
      res.writeHead(404);
      res.end();
    });

    this.wss = new WebSocketServer({ server: this.server });
    this.wss.on('error', (err) => console.error('ROME WS error:', err));

    return new Promise(async (resolve, reject) => {
      this.server!.on('error', reject);
      this.server!.listen(this.port, "0.0.0.0", () => {
        const addr = this.server!.address();
        const actualPort = typeof addr === 'object' && addr !== null ? addr.port : this.port;
        console.log(`ROME Peer Server (${this.capability}) started on port ${actualPort}`);
        resolve(actualPort);
      });

      this.wss!.on('connection', (ws, req) => {
        ws.on('message', (raw) => {
          try {
            const msg = JSON.parse(raw.toString()) as RomeMessage;
            if (msg.type === 'command') this.handleCommand(ws, msg);
            else if (msg.type === 'agent_hello') {
              const p = msg.payload || {};
              this.workers.register(ws, p.capabilities, p.version, p.platform, p.peer_url, p.one_shot ?? true);
              ws.send(JSON.stringify({ type: 'worker_ack', ok: true, payload: { message: 'Registered', capabilities_accepted: p.capabilities } }));
              this.scheduleTick();
            }
            else if (msg.type === 'event') this.handleWorkerEvent(ws, msg);
          } catch (e) {
            console.error('ROME Peer Server: message error:', e);
          }
        });

        let isReplaying = true;
        const busSub = (ev: RomeEvent) => {
          if (ws.readyState === WebSocket.OPEN) {
            if (isReplaying) {
              const evTime = (ev as any).timestamp ?? (ev.ts ? ev.ts * 1000 : Date.now());
              if (Date.now() - evTime > this.eventReplayWindow) {
                return;
              }
            }
            ws.send(JSON.stringify({ type: 'event', event: ev }));
          }
        };
        this.bus.subscribe(busSub);
        isReplaying = false;
        ws.on('close', () => {
          this.bus.unsubscribe(busSub);
          const orphaned = this.workers.unregister(ws);
          for (const tid of orphaned) {
            this.registry.update(tid, 'failed', { error: 'worker disconnected' });
            this.bus.broadcast({ type: 'error', task_id: tid, payload: { message: 'worker disconnected' } });
          }
          this.scheduleTick();
        });
        ws.send(JSON.stringify({
          type: 'daemon_hello',
          version: getRomeVersion(),
          platform: process.platform,
          capabilities: Object.keys(this.arsenal),
          uptime_s: (Date.now() / 1000) - this.startTime
        }));
      });
    });
  }

  stop() {
    this.wss?.close();
    this.server?.close();
    this.activeSubprocesses.forEach(p => {
      try {
        p.kill();
      } catch {
        // Process already exited, ignore ESRCH
      }
    });
  }

  private async loadProjectTotals() {
    const logPath = path.join(ROME_ROOT, 'logs', 'rome.jsonl');
    try {
      if (fs.existsSync(logPath)) {
        const logContent = await fs.promises.readFile(logPath, 'utf-8');
        for (const line of logContent.split('\n')) {
          if (!line) continue;
          try {
            const entry = JSON.parse(line);
            // FIX 4 (line ~220): Change `entry.status === 'SUCCESS' && entry.usage` to `entry.usage`
            if (entry.usage) { 
              this.projectTotalCost += entry.usage.cost_usd || 0;
              this.projectTotalTokens += entry.usage.total_tokens || 0;
            }
          } catch (e) {
            console.error(`ROME: Failed to parse log entry: ${line}`, e);
          }
        }
      }
    } catch (e) {
      console.error(`ROME: Failed to read or process log file ${logPath}:`, e);
    }
  }

  getPort(): number {
    const addr = this.server?.address();
    return typeof addr === 'object' && addr !== null ? addr.port : this.port;
  }

  private handleWorkerEvent(ws: WebSocket, msg: RomeMessage) {
    const { event } = msg as any;
    const type = event?.type;
    const tid = event?.task_id;
    const p = event?.payload || {};
    
    switch (type) {
      case 'progress':
        this.registry.updateProgress(tid, p.percent, p.message); 
        this.bus.broadcast({ type: 'progress', task_id: tid, payload: p }); 
        break;
      case 'complete':
        const status = ['SUCCESS', 'OK', 'COMPLETED'].includes(String(p.status).toUpperCase()) ? 'completed' : 'failed';
        if (p.report && tid) {
          const task = this.registry.get(tid);
        }
        const usage = p.usage ? { ...p.usage, cost_usd: p.usage.cost_usd ?? undefined } : undefined;
        this.registry.update(tid, status, p, usage);
        this.processStateReduction(tid);
        if (p.report && tid) this.applyStateSignals(p.report, tid);
        this.bus.broadcast({ type: 'complete', task_id: tid, payload: p });
        this.workers.markIdle(ws, tid);
        if (this.workers.isOneShot(ws)) ws.close();
        if (status === 'failed' && isQuotaError(p.report || p.error || '')) { const t = this.registry.get(tid); if (t) this.markCapabilityDown(t.capability, p.report || p.error || ''); }
        this.logUsage('worker', status, tid, p.usage);
        this.scheduleTick();
        break;
      case 'error':
        this.registry.update(tid, 'failed', { error: p.message });
        this.bus.broadcast({ type: 'error', task_id: tid, payload: p });
        this.workers.markIdle(ws, tid);
        if (isQuotaError(p.message || '')) { const t = this.registry.get(tid); if (t) this.markCapabilityDown(t.capability, p.message); }
        this.scheduleTick();
        break;
    }
  }

  private logUsage(tool: string, status: string, task_id: string, usage: any) {
    const logPath = path.join(ROME_ROOT, 'logs', 'rome.jsonl');
    const entry = JSON.stringify({ ts: Date.now() / 1000, tool, task_id, status, usage }) + '\n';
    fs.promises.appendFile(logPath, entry).catch(() => {});

    // Update project totals if status is SUCCESS and usage is available
    // FIX 4 (line ~282): Change `status === 'SUCCESS' && usage` to `usage`
    if (usage) {
      this.projectTotalCost += usage.cost_usd || 0;
      this.projectTotalTokens += usage.total_tokens || 0;
    }
  }

  private async handleCommand(ws: WebSocket, msg: RomeMessage) {
    const { command, request_id, payload } = msg;
    switch (command) {
      case 'ping': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { pong: true } })); break;
      case 'state_get': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { key: payload?.key, value: this.blackboard.get(payload?.key) } })); break;
      case 'state_delete': { const ok = this.blackboard.delete(payload?.key); if (ok) this.bus.broadcast({ type: 'state_changed', task_id: '', payload: { key: payload?.key, value: undefined } }); ws.send(JSON.stringify({ type: 'response', request_id, ok })); break; }
      case 'state_get_meta': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { key: payload?.key, meta: this.blackboard.getMeta(payload?.key) } })); break;
      case 'state_set': {
        const { key, value, caused_by_task } = payload || {};
        if (!key || !caused_by_task) {
          ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: 'Missing key or caused_by_task' }));
          break;
        }
        const task = this.registry.get(caused_by_task);
        const update = { key, value, caused_by_task, task_ts: task ? task.ts : (Date.now() / 1000) };
        const success = this.blackboard.set(update);
        if (success) {
          this.bus.broadcast({ type: 'state_changed', task_id: caused_by_task, payload: { key, value } });
        }
        ws.send(JSON.stringify({ type: 'response', request_id, ok: success, payload: { success } }));
        break;
      }
      case 'dispatch': {
        const task_id = payload.task_id || `ts-${uuidv4().substring(0, 8)}`;
        let capability = (payload.capability || this.capability).toUpperCase();
        const prompt = payload.prompt || '';
        
        const distilledPrompt = await this.aaak.preDispatch(this.buildBlackboardContext(prompt, capability), payload.goal || prompt.slice(0, 200), capability);

        const CACHEABLE = !['NATIVE_SHELL', 'SAFE_SHELL', 'TEST'].includes(capability);
        if (CACHEABLE) {
          const cached = await this.semanticCache.get(capability, prompt);
          if (cached) {
            this.registry.register(task_id, capability, prompt, payload.parent_task_id, payload.goal, payload.intent);
            this.registry.update(task_id, 'running');
            this.registry.update(task_id, 'completed', cached, undefined);
            this.bus.broadcast({ type: 'complete', task_id, payload: cached });
            ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'cache' } }));
            break;
          }
        }

        if (capability === 'NATIVE_SHELL') {
          this.registry.register(task_id, 'NATIVE_SHELL', prompt, undefined, prompt.slice(0, 50), 'Native Daemon Shell');
          this.registry.update(task_id, 'running');
          this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability: 'NATIVE_SHELL' } });
          this.scheduleTick();
          this.runNativeShell(ws, request_id || '', prompt, task_id);
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'native_shell' } }));
          break;
        }

        this.registry.register(task_id, capability, prompt, payload.parent_task_id, payload.goal, payload.intent);
        this.registry.update(task_id, 'running');
        this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability, goal: payload.goal, intent: payload.intent } });
        this.scheduleTick();
        const probe = this.probeResults[capability];
        if (probe && !probe.available) {
          this.registry.update(task_id, 'failed', { error: `${capability} unavailable: ${probe.reason}` });
          this.bus.broadcast({ type: 'error', task_id, payload: { message: `${capability} unavailable: ${probe.reason}` } });
          ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: `${capability} unavailable: ${probe.reason}`, payload: { task_id } }));
          break;
        }
        const workerWs = this.workers.findWorker(capability);
        if (workerWs) {
          this.workers.markBusy(workerWs, task_id);
          workerWs.send(JSON.stringify({ type: 'command', command: 'dispatch', request_id: `fwd-${task_id}`, payload: { task_id, capability, prompt: distilledPrompt } }));
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'worker' } }));
        } else {
          this.runLegion(task_id, capability, distilledPrompt, prompt);
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'subprocess' } }));
        }
        break;
      }
      case 'native_shell': {
        const task_id = `ts-${uuidv4().substring(0, 8)}`;
        const cmdStr = payload.command || '';
        this.registry.register(task_id, 'NATIVE_SHELL', cmdStr, undefined, cmdStr.slice(0, 50), 'Native Daemon Shell');
        this.registry.update(task_id, 'running');
        this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability: 'NATIVE_SHELL', goal: cmdStr.slice(0, 50), intent: 'Native Daemon Shell' } });
        this.scheduleTick();
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true } }));
        this.runNativeShell(ws, request_id || '', cmdStr, task_id);
        break;
      }
      case 'get_state': {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: {
          tasks: Object.fromEntries(this.registry.getAll().filter(t => t.status === "pending" || t.status === "running" || (Date.now() / 1000) - t.ts < 300).map(t => [t.task_id, t])),
          workers: this.workers.getInfo(),
          ...this.registry.getSessionStats(),
          uptime_s: (Date.now() / 1000) - this.startTime,
          state: this.blackboard.get()
        } }));
        break;
      }
      case 'status': {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { 
          tasks: Object.fromEntries(this.registry.getAll().filter(t => t.status === "pending" || t.status === "running" || (Date.now() / 1000) - t.ts < 300).map(t => [t.task_id, t])), 
          workers: this.workers.getInfo(), 
          ...this.registry.getSessionStats(), 
          uptime_s: (Date.now() / 1000) - this.startTime,
          state: this.blackboard.get(),
          // Add project-wide totals
          project_total_cost_usd: this.projectTotalCost,
          project_total_tokens: this.projectTotalTokens
        } }));
        break;
      }
      case 'workers': {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { workers: this.workers.getInfo() } }));
        break;
      }
      case 'probe_arsenal': {
        // Re-probe on demand. Dashboard "recheck" button / manual refresh.
        this.probeResults = await probeArsenal(this.arsenal);
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { capabilities: this.probeResults } }));
        break;
      }

      case 'aaak_recall': {
        const query = payload.query || '';
        const limit = typeof payload.limit === 'number' ? payload.limit : 7;
        const facts = await this.aaak.store.query(query, limit);
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { facts } }));
        break;
      }
      case 'aaak_seed': {
        const content = payload.content || '';
        if (!content) {
          ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: 'content required', payload: {} }));
          break;
        }
        const fact = { content, ts: Date.now() / 1000, ...(payload.meta || {}) };
        this.aaak.store.save(fact).catch(() => {});
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { saved: true } }));
        break;
      }
      case 'reset': this.registry.clearAll(); this.bus.broadcast({ type: 'reset', task_id: '', payload: { cleared: true } }); ws.send(JSON.stringify({ type: 'response', request_id, ok: true })); break;
    }
  }

  private runNativeShell(ws: WebSocket, request_id: string, command: string, taskId?: string) {
    console.log(`[NS] Executing: ${command}`);
    const proc = spawn(command, [], { 
      cwd: ROME_ROOT, 
      env: { ...process.env, FORCE_COLOR: '1' }, 
      shell: '/bin/bash' 
    });
    let output = '';
    if (proc.stdout) proc.stdout.on('data', (d) => { output += d.toString(); });
    if (proc.stderr) proc.stderr.on('data', (d) => { output += d.toString(); });
    
    proc.on('close', (code) => {
      console.log(`[NS] Finished [${code}]: ${command.slice(0, 30)}`);
      if (taskId) {
        this.registry.update(taskId, code === 0 ? 'completed' : 'failed', { report: output });
        this.applyStateSignals(output, taskId);
        this.bus.broadcast({ type: 'complete', task_id: taskId, payload: { status: code === 0 ? 'SUCCESS' : 'FAILED', report: output } });
        this.scheduleTick();
      } else {
        try {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'response', request_id, ok: code === 0, payload: { output, code } }));
          }
        } catch {}
      }
    });
    if (taskId) this.activeSubprocesses.set(taskId, { kill: () => {
      try { process.kill(proc.pid!, 'SIGTERM'); } catch {}
    }});
  }

  private runLegion(task_id: string, capability: string, prompt: string, rawPrompt?: string) {
    const wsSender = async (ev: any) => this.bus.broadcast({ ...ev, task_id });
    const cap = this.arsenal[capability];
    if (!cap) {
      this.registry.update(task_id, 'failed', { error: `Unknown capability: ${capability}` });
      this.bus.broadcast({ type: 'error', task_id, payload: { message: `Unknown capability: ${capability}` } });
      return;
    }
    if (cap.type === 'shell') {
      // FIX 1: SAFE_SHELL zombie timeout
      const cancelEmitter = new EventEmitter();
      const SHELL_TIMEOUT_MS = 90_000;
      const shellTimer = setTimeout(() => cancelEmitter.emit('timeout', task_id), SHELL_TIMEOUT_MS);
      
      executeShell(task_id, prompt, wsSender, cancelEmitter).then(res => {
        clearTimeout(shellTimer);
        this.registry.update(task_id, res.status === 'SUCCESS' ? 'completed' : 'failed', res);
        if (res.status === 'SUCCESS') {
          this.aaak.postResult(res as any, capability).catch(() => {});
          if (!['SAFE_SHELL', 'NATIVE_SHELL', 'TEST'].includes(capability)) {
            this.semanticCache.set(capability, rawPrompt || prompt, res as any).catch(() => {});
          }
        }
        this.bus.broadcast({ type: 'complete', task_id, payload: res });
        this.logUsage('shell', res.status, task_id, null);
        this.scheduleTick();
      }).catch(e => { // Added catch block for executeShell
        clearTimeout(shellTimer); // Clear timer on error
        console.error(`ROME: executeShell failed for task ${task_id}:`, e);
        this.registry.update(task_id, 'failed', { error: e.message });
        this.bus.broadcast({ type: 'error', task_id, payload: { message: e.message } });
        if (isQuotaError(e.message || '')) this.markCapabilityDown(capability, e.message);
        this.scheduleTick();
      });
    } else {
      const model = cap.model || 'gemini-3.1-pro-preview';
      const effectivePrompt = cap.system_prompt ? `${cap.system_prompt}

TASK: ${prompt}` : prompt;
      const finalArgs = (cap.args || []).map((a: any) => typeof a === 'string' ? a.replace(/{MODEL}/g, model) : a).concat(effectivePrompt);
      executeTask(task_id, capability, finalArgs, wsSender).then(manifest => {
        const usage = manifest.usage ? { ...manifest.usage, cost_usd: manifest.usage.cost_usd ?? undefined } : undefined;
        this.registry.update(task_id, manifest.status === 'SUCCESS' ? 'completed' : 'failed', manifest, usage);
        if (manifest.status === 'SUCCESS') this.aaak.postResult(manifest, capability).catch(() => {});
        if (manifest.status === 'SUCCESS' && !['SAFE_SHELL', 'NATIVE_SHELL', 'TEST'].includes(capability)) {
          this.semanticCache.set(capability, rawPrompt || prompt, manifest).catch(() => {});
        }
        this.bus.broadcast({ type: 'complete', task_id, payload: manifest });
        this.logUsage('legion', manifest.status, task_id, manifest.usage);
        this.scheduleTick();
      }).catch(e => {
        this.registry.update(task_id, 'failed', { error: e.message });
        this.bus.broadcast({ type: 'error', task_id, payload: { message: e.message } });
        if (isQuotaError(e.message || '')) this.markCapabilityDown(capability, e.message);
        this.scheduleTick();
      });
    }
  }


  private applyStateSignals(report: string, task_id: string) {
    for (const sig of extractStateSignals(report)) {
      const task = this.registry.get(task_id);
      const update = { key: sig.key, value: sig.value, caused_by_task: task_id, task_ts: task ? task.ts : (Date.now() / 1000) };
      if (this.blackboard.set(update)) {
        this.bus.broadcast({ type: 'state_changed', task_id, payload: { key: sig.key, value: sig.value } });
      }
    }
  }

  private buildBlackboardContext(prompt: string, capability: string): string {
    const capConfig = this.arsenal[capability];
    if (capConfig?.type === 'shell') return prompt;

    const state = this.blackboard.get() as Record<string, any>;
    const keys = Object.keys(state);
    if (keys.length === 0) return prompt;

    const now = Date.now() / 1000;
    const TTL = 7200;
    const fresh: Record<string, any> = {};
    let count = 0;
    for (const key of keys) {
      if (count >= 20) break;
      const meta = this.blackboard.getMeta(key);
      if (meta && (now - meta.task_ts) > TTL) continue;
      const val = state[key];
      const str = typeof val === 'string' ? val : JSON.stringify(val);
      fresh[key] = str.length > 200 ? str.slice(0, 200) + '…' : str;
      count++;
    }

    if (Object.keys(fresh).length === 0) return prompt;
    return `<blackboard>
${JSON.stringify(fresh)}
</blackboard>

${prompt}`;
  }

  private markCapabilityDown(capability: string, reason: string) {
    if (!this.probeResults[capability]) return;
    this.probeResults[capability] = { ...this.probeResults[capability], available: false, reason };
    console.warn(`ROME: capability ${capability} marked unavailable — ${reason}`);
  }

  private scheduleTick() {
    if (this.tickScheduled) return;
    this.tickScheduled = true;
    queueMicrotask(() => {
      this.tickScheduled = false;
      this.tick();
    });
  }

  private tick() {
    // Reap zombie tasks (pending > 600s — covers max arsenal.timeout)
    for (const t of this.registry.getAll().filter(t => t.status === "pending" || t.status === "running" || (Date.now() / 1000) - t.ts < 300)) {
      if (t.status === 'pending' && (Date.now() / 1000) - t.ts > 600) {
        this.registry.update(t.task_id, 'failed', { error: 'Task timeout (zombie)' });
        this.bus.broadcast({ type: 'error', task_id: t.task_id, payload: { message: 'Task timeout (zombie)' } });
      }
    }

    // Heartbeat
    this.bus.broadcast({ type: 'heartbeat', task_id: '', payload: {} });

    // System status
    this.bus.broadcast({
      type: 'system_status',
      task_id: '',
      payload: {
        uptime_s: (Date.now() / 1000) - this.startTime,
        agents: this.workers.getInfo(),
        capability: this.capability,
        capabilities_probe: this.probeResults,
        ...this.registry.getSessionStats()
      }
    });
  }

  private processStateReduction(taskId: string) {
    const task = this.registry.get(taskId);
    if (!task || task.status !== 'completed') return;
    this.reducer.reduce(task);
  }
}

import { fileURLToPath } from 'url';
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  new PeerServer(process.argv[2] || 'GEMINI', process.argv[3] ? parseInt(process.argv[3]) : undefined).start();
}
