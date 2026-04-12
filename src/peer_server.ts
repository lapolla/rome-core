import { WebSocketServer, WebSocket } from 'ws';
import { v4 as uuidv4 } from 'uuid';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';
import { exec } from 'child_process';
import type { RomeMessage, TaskInfo, TaskUsage } from './rome_types.js';
import { EventBus, TaskRegistry, WorkerRegistry } from './registry.js';
import { executeTask } from './legion_worker.js';
import { executeShell } from "./shell_executor.js";
import { AAAK } from "./aaak/index.js";

const TOKEN = process.env.ROME_WS_TOKEN || "ROME_V4_SECURE_TOKEN";
const ROME_ROOT = process.env.ROME_ROOT || process.cwd();

// Ensure node-global CLIs (gemini, codex, claude) are reachable from spawned children.
{
  const nodeBinDir = path.dirname(process.execPath);
  const currentPath = process.env.PATH ?? '';
  if (!currentPath.split(':').includes(nodeBinDir)) {
    process.env.PATH = `${nodeBinDir}:${currentPath}`;
  }
}
const FALLBACK_CHAIN: Record<string, string> = { "GEMINI": "CODEX", "CODEX": "MISTRAL" };
const BUSY_PATTERNS = ["service temporarily unavailable", "overloaded", "rate_limit", "rate limit", "quota", "503", "429", "capacity"];

function loadArsenal(romeRoot: string) {
  const arsenalPath = path.join(romeRoot, 'arsenal', 'core_arsenal.json');
  if (!fs.existsSync(arsenalPath)) return {};
  const raw = JSON.parse(fs.readFileSync(arsenalPath, 'utf-8'));
  const geminiCli = 'gemini'; 

  const resolve = (val: any): any => {
    if (typeof val === 'string') return val.replace(/{ROME_ROOT}/g, romeRoot).replace(/{GEMINI_CLI}/g, geminiCli);
    if (Array.isArray(val)) return val.map(resolve);
    if (typeof val === 'object' && val !== null) {
      const res: any = {};
      for (const [k, v] of Object.entries(val)) res[k] = resolve(v);
      return res;
    }
    return val;
  };

  const caps: any = {};
  for (const [name, cap] of Object.entries(raw.capabilities || {})) caps[name.toUpperCase()] = resolve(cap);
  return caps;
}

export class PeerServer {
  private capability: string;
  private port: number;
  private bus = new EventBus();
  private registry = new TaskRegistry();
  private workers = new WorkerRegistry();
  private activeSubprocesses = new Map<string, { kill: () => void }>();
  private arsenal: any;
  private aaak: AAAK;
  private wss?: WebSocketServer;
  private server?: http.Server;
  private startTime = Date.now() / 1000;
  private intervals: NodeJS.Timeout[] = [];

  constructor(capability: string, port?: number) {
    this.capability = capability.toUpperCase();
    this.arsenal = loadArsenal(ROME_ROOT);
    this.aaak = new AAAK("default", { enabled: true });
    const cap = this.arsenal[this.capability];
    this.port = port !== undefined ? port : (cap?.peer_port || 8741);
  }

  private isBusy(output: string): boolean {
    const low = output.toLowerCase();
    return BUSY_PATTERNS.some(p => low.includes(p));
  }

  private recommendCapability(prompt: string): string {
    const desc = prompt.toLowerCase();
    const kwGemini = ["review", "analyze", "security", "architect", "complex", "audit", "refactor", "design"];
    const kwCodex = ["fix", "implement", "update", "write", "add", "small", "patch", "rename"];
    const kwShell = ["grep", "build", "test", "find", "run", "execute", "shell", "bash", "compile", "move", "copy", "delete"];
    const scores = {
      GEMINI: kwGemini.filter(k => desc.includes(k)).length,
      CODEX: kwCodex.filter(k => desc.includes(k)).length,
      SAFE_SHELL: kwShell.filter(k => desc.includes(k)).length
    };
    if (scores.SAFE_SHELL > scores.GEMINI && scores.SAFE_SHELL > scores.CODEX) return "SAFE_SHELL";
    if (scores.GEMINI >= scores.CODEX) return "GEMINI";
    return "CODEX";
  }

  start() {
    this.server = http.createServer((req, res) => {
      const url = new URL(req.url || '', `http://${req.headers.host}`);
      if (url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', uptime: (Date.now() / 1000) - this.startTime }));
        return;
      }
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
    this.server.listen(this.port, () => {
      console.log(`ROME Peer Server (${this.capability}) started on port ${this.port}`);
      console.log(`Dashboard available at http://localhost:${this.port}/dashboard/`);
    });

    this.wss.on('connection', (ws, req) => {
      const url = new URL(req.url || '', `http://${req.headers.host}`);
      // Same-origin dashboard connections bypass auth (browser can't set Authorization on WS upgrade)
      let sameOrigin = false;
      const origin = req.headers.origin;
      if (origin) {
        try { sameOrigin = new URL(origin).host === req.headers.host; } catch { /* bad origin */ }
      }
      if (!sameOrigin && url.searchParams.get('token') !== TOKEN && req.headers['authorization'] !== `Bearer ${TOKEN}`) {
        ws.close(1008, 'Unauthorized'); return;
      }
      let isWorker = false;
      this.bus.subscribe(ws);
      ws.send(JSON.stringify({ type: 'daemon_hello', version: '6.0.0', platform: process.platform, capabilities: Object.keys(this.arsenal), uptime_s: (Date.now() / 1000) - this.startTime }));
      ws.on('message', async (data) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.type === 'agent_hello') {
            const p = msg.payload || {};
            const caps = Array.isArray(p.capabilities) ? p.capabilities : [];
            if (caps.length === 0) {
              console.log(`[MESH] Ignoring worker registration with empty capabilities`);
              return;
            }
            console.log(`[MESH] Registering worker ${ws.url} with caps:`, caps);
            this.workers.register(ws, caps, p.version, p.platform, p.peer_url);
            isWorker = true;
            ws.send(JSON.stringify({ type: 'worker_ack', ok: true, payload: { message: 'Registered', capabilities_accepted: caps } }));
            return;
          }
          if (msg.type === 'event' && isWorker) { this.handleWorkerEvent(ws, msg.event); return; }
          if (msg.type === 'command') await this.handleCommand(ws, msg);
        } catch (e) { console.error('Error handling message:', e); }
      });
      ws.on('close', () => {
        if (isWorker) this.workers.unregister(ws).forEach(tid => this.registry.update(tid, 'failed', { error: 'Worker disconnected' }));
        this.bus.unsubscribe(ws);
      });
    });
    this.intervals.push(setInterval(() => this.bus.broadcast({ type: 'heartbeat', task_id: '', payload: {} }), 15000));
    this.intervals.push(setInterval(() => this.reapZombies(), 60000));
    this.intervals.push(setInterval(() => this.broadcastSystemStatus(), 15000));
  }

  private broadcastSystemStatus() {
    const stats = this.registry.getSessionStats();
    this.bus.broadcast({
      type: 'system_status',
      task_id: '',
      payload: {
        uptime_s: (Date.now() / 1000) - this.startTime,
        agents: this.workers.getInfo(),
        capability: this.capability,
        ...stats
      }
    });
  }

  private reapZombies() {
    const now = Date.now() / 1000;
    this.registry.getAll().forEach(t => {
      if (['pending', 'running'].includes(t.status) && (t.progress_percent || 0) === 0 && now - (t.updated_at || t.ts) > 180) {
        this.registry.update(t.task_id, 'failed', { error: 'Reaped: zombie task' });
        this.bus.broadcast({ type: 'error', task_id: t.task_id, payload: { message: 'Reaped: zombie task' } });
      }
    });
  }

  stop() { 
    if (this.wss) this.wss.close(); 
    if (this.server) this.server.close();
    this.intervals.forEach(clearInterval); 
  }

  private handleWorkerEvent(ws: WebSocket, event: any) {
    const { type, task_id, payload } = event;
    switch (type) {
      case 'progress': this.registry.updateProgress(task_id, payload.percent, payload.message); this.bus.broadcast({ type: 'progress', task_id, payload }); break;
      case 'complete':
        const status = ['SUCCESS', 'OK', 'COMPLETED'].includes(String(payload.status).toUpperCase()) ? 'completed' : 'failed';
        
        // AAAK Hook: Post-result for remote workers
        if (payload.report && task_id) {
          const task = this.registry.get(task_id);
          this.aaak.postResult({
            task_id,
            status: payload.status,
            report: payload.report,
            usage: payload.usage
          }, task?.prompt || "");
        }

        const resultPayload = { ...(payload.result || payload), report: payload.report };
        this.registry.update(task_id, status, resultPayload, payload.usage);
        this.bus.broadcast({ type: 'complete', task_id, payload });
        this.workers.markIdle(ws, task_id);
        this.logUsage('worker', status, task_id, payload.usage);
        break;
      case 'error': this.registry.update(task_id, 'failed', { error: payload.message }); this.bus.broadcast({ type: 'error', task_id, payload }); this.workers.markIdle(ws, task_id); break;
    }
  }

  private logUsage(tool: string, status: string, task_id: string, usage: any) {
    const logPath = path.join(ROME_ROOT, 'logs', 'rome.jsonl');
    const entry = JSON.stringify({ ts: Date.now() / 1000, tool, task_id, status, usage }) + '\n';
    try { fs.appendFileSync(logPath, entry); } catch (e) {}
  }

  private async handleCommand(ws: WebSocket, msg: RomeMessage) {
    const { command, request_id, payload } = msg;
    switch (command) {
      case 'dispatch': {
        const task_id = payload.task_id || `ts-${uuidv4().substring(0, 8)}`;
        let capability = (payload.capability || this.capability).toUpperCase();
        const prompt = payload.prompt || '';
        if (capability === 'AUTO') capability = this.recommendCapability(prompt);
        
        // AAAK Hook: Pre-dispatch
        const distilledPrompt = this.aaak.preDispatch(prompt, '', capability);

        this.registry.register(task_id, capability, prompt, payload.parent_task_id, payload.goal, payload.intent);
        this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability, goal: payload.goal, intent: payload.intent } });
        const workerWs = this.workers.findWorker(capability);
        if (workerWs) {
          this.workers.markBusy(workerWs, task_id);
          workerWs.send(JSON.stringify({ type: 'command', command: 'dispatch', request_id: `fwd-${task_id}`, payload: { task_id, capability, prompt: distilledPrompt } }));
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'worker' } }));
        } else {
          this.runLegion(task_id, capability, distilledPrompt);
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'subprocess' } }));
        }
        break;
      }
      case 'native_shell': {
        const task_id = `ts-${uuidv4().substring(0, 8)}`;
        const cmdStr = payload.command || '';
        this.registry.register(task_id, 'NATIVE_SHELL', cmdStr, undefined, cmdStr.slice(0, 50), 'Native Daemon Shell');
        this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability: 'NATIVE_SHELL', goal: cmdStr.slice(0, 50), intent: 'Native Daemon Shell' } });
        this.runNativeShell(ws, request_id || '', cmdStr, task_id);
        break;
      }
      case 'status': {
        const task_id = payload.task_id;
        const tasksObj = Object.fromEntries(this.registry.getAll().map(t => [t.task_id, t]));
        const stats = this.registry.getSessionStats();
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: task_id ? this.registry.get(task_id) : { tasks: tasksObj, workers: this.workers.getInfo(), ...stats, uptime_s: (Date.now() / 1000) - this.startTime } }));
        break;
      }
      case 'dashboard_stats': {
        const tasks = this.registry.getAll();
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { total_tasks: tasks.length, completed: tasks.filter(t => t.status === 'completed').length, failed: tasks.filter(t => t.status === 'failed').length, running: tasks.filter(t => t.status === 'running').length, usage: this.registry.getUsage(), uptime_s: (Date.now() / 1000) - this.startTime } }));
        break;
      }
      case 'await': {
        const tids: string[] = Array.isArray(payload.task_ids) ? payload.task_ids : [payload.task_id];
        const results = await Promise.all(tids.map((tid: string) => this.registry.awaitTask(tid, (payload.timeout || 300) * 1000)));
        ws.send(JSON.stringify({ type: 'response', request_id, ok: results.every(r => r && ['completed', 'success'].includes(r.status.toLowerCase())), payload: { tasks: results.filter(r => r !== null) } }));
        break;
      }
      case 'read_file': {
        const filePath = path.resolve(payload.path.replace(/^~/, process.env.HOME || ''));
        try {
          const lines = fs.readFileSync(filePath, 'utf-8').split('\n');
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { path: filePath, content: (payload.end_line ? lines.slice((payload.start_line || 1) - 1, payload.end_line) : lines.slice((payload.start_line || 1) - 1)).join('\n'), total_lines: lines.length } }));
        } catch (e: any) { ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: e.message })); }
        break;
      }
      case 'write_file': {
        const filePath = path.resolve(payload.path.replace(/^~/, process.env.HOME || ''));
        try {
          fs.mkdirSync(path.dirname(filePath), { recursive: true });
          fs.writeFileSync(filePath, payload.content, 'utf-8');
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { path: filePath, size: payload.content.length } }));
        } catch (e: any) { ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: e.message })); }
        break;
      }
      case 'list_dir': {
        const dirPath = path.resolve(payload.dir_path || '.');
        try {
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { dir_path: dirPath, entries: fs.readdirSync(dirPath, { withFileTypes: true }).map(e => ({ name: e.name, type: e.isDirectory() ? 'directory' : 'file', path: path.join(dirPath, e.name) })) } }));
        } catch (e: any) { ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: e.message })); }
        break;
      }
      case 'cancel': {
        const task_id = payload.task_id;
        this.registry.update(task_id, 'cancelled');
        const localProc = this.activeSubprocesses.get(task_id);
        if (localProc) {
          localProc.kill();
          this.activeSubprocesses.delete(task_id);
        }
        const workerWs = this.workers.findWorkerByTask(task_id);
        if (workerWs) workerWs.send(JSON.stringify({ type: 'interrupt', task_id }));
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: 'cancelled', ok: false, report: 'Task cancelled by user.' } });
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, cancelled: true } }));
        break;
      }
      case 'reset': {
        this.registry.clearAll();
        this.bus.broadcast({ type: 'reset', task_id: '', payload: { cleared: true } });
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { cleared: true } }));
        break;
      }
      case 'clear': {
        this.registry.clearFinished();
        this.bus.broadcast({ type: 'clear', task_id: '', payload: { cleared: true } });
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { cleared: true } }));
        break;
      }
      case 'get_state': {
        const tasksObj = Object.fromEntries(this.registry.getAll().map(t => [t.task_id, t]));
        const stats = this.registry.getSessionStats();
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { tasks: tasksObj, workers: this.workers.getInfo(), session_cost_usd: stats.session_cost_usd, session_worker_tokens: stats.session_worker_tokens, uptime_s: (Date.now() / 1000) - this.startTime } }));
        break;
      }
      case 'workers': {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { ok: true, workers: this.workers.getInfo(), count: this.workers.count() } }));
        break;
      }
      case 'recent_events': {
        const since_ts = payload.since_ts || 0;
        const limit = payload.limit || 10;
        let events = this.bus.getRecent(limit);
        if (since_ts) events = events.filter(e => e.ts >= since_ts);
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { events } }));
        break;
      }
      case 'submit_result': {
        const task_id = payload.task_id;
        this.registry.update(task_id, payload.status, payload.result, payload.usage);
        this.bus.broadcast({ type: 'complete', task_id, payload });
        const workerWs = this.workers.findWorkerByTask(task_id);
        if (workerWs) this.workers.markIdle(workerWs, task_id);
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true }));
        break;
      }
      case 'report_usage': {
        this.registry.addUsage(payload.tokens || 0, payload.cost_usd || 0);
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { tokens_logged: payload.tokens } }));
        break;
      }
      case 'event': {
        this.bus.broadcast(payload);
        if (payload.type === 'complete' && payload.task_id) {
          const s = String(payload.payload?.status ?? '').toUpperCase();
          const resolved = ['SUCCESS', 'OK', 'COMPLETED'].includes(s) ? 'completed' : 'failed';
          this.registry.update(payload.task_id, resolved, payload.payload, payload.payload?.usage);
        } else if (payload.type === 'progress' && payload.task_id) {
          this.registry.updateProgress(payload.task_id, payload.payload?.percent ?? 0, payload.payload?.message ?? '');
        }
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true }));
        break;
      }
      case 'interrupt': {
        const task_id = payload.task_id;
        const localProc = this.activeSubprocesses.get(task_id);
        if (localProc) {
          localProc.kill();
          this.activeSubprocesses.delete(task_id);
        }
        const workerWs = this.workers.findWorkerByTask(task_id);
        if (workerWs) workerWs.send(JSON.stringify({ type: 'interrupt', task_id }));
        this.registry.update(task_id, 'cancelled');
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: 'cancelled', ok: false, report: 'Interrupted by user.' } });
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true }));
        break;
      }
      case 'ping': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { pong: true, ts: Date.now() / 1000 } })); break;
      default: ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: `Unknown command: ${command}` }));
    }
  }

  private runNativeShell(ws: WebSocket, request_id: string, command: string, taskId?: string) {
    const proc = exec(command, { encoding: 'utf-8', shell: '/bin/bash', cwd: ROME_ROOT }, (error, stdout, stderr) => {
      this.activeSubprocesses.delete(request_id);
      const exitCode = (error as any)?.code || 0;
      const ok = exitCode === 0;
      const report = stdout || (error ? error.message : '');

      if (taskId) {
        const status = ok ? 'completed' : 'failed';
        this.registry.update(taskId, status, { report, exit_code: exitCode });
        this.bus.broadcast({ type: 'complete', task_id: taskId, payload: { status: ok ? 'SUCCESS' : 'FAILED', report, exit_code: exitCode } });
      }

      if (error) {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: false, payload: { report, exit_code: exitCode } }));
      } else {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { report, exit_code: 0 } }));
      }
    });
    if (proc.pid) {
      this.activeSubprocesses.set(request_id, { kill: () => { try { process.kill(proc.pid!, 'SIGTERM'); } catch (_) {} } });
    }
  }

  private async runLegion(task_id: string, capability: string, prompt: string) {
    const cap = this.arsenal[capability];
    if (!cap) { this.registry.update(task_id, 'failed', { error: `Unknown capability: ${capability}` }); return; }
    const taskDir = path.join(ROME_ROOT, 'legions', task_id);
    fs.mkdirSync(taskDir, { recursive: true });

    const signalHandler = async (signal: any): Promise<object> => {
      switch (signal.type) {
        case 'dispatch': {
          const sub_task_id = `ts-${uuidv4().substring(0, 8)}`;
          const sub_cap = (signal.capability || 'SAFE_SHELL').toUpperCase();
          const sub_prompt = signal.prompt || '';
          this.registry.register(sub_task_id, sub_cap, sub_prompt, task_id);
          this.bus.broadcast({ type: 'dispatch_start', task_id: sub_task_id, payload: { capability: sub_cap, parent_task_id: task_id } });
          const workerWs = this.workers.findWorker(sub_cap);
          if (workerWs) {
            this.workers.markBusy(workerWs, sub_task_id);
            workerWs.send(JSON.stringify({ type: 'command', command: 'dispatch', request_id: `fwd-${sub_task_id}`, payload: { task_id: sub_task_id, capability: sub_cap, prompt: sub_prompt } }));
          } else {
            this.runLegion(sub_task_id, sub_cap, sub_prompt);
          }
          return { ok: true, task_id: sub_task_id };
        }
        case 'await': {
          const res = await this.registry.awaitTask(signal.task_id, 300000); // 5 min default
          return res ? { ok: true, ...res } : { ok: false, error: 'Task not found or timed out' };
        }
        case 'shell': {
          const res = await executeShell(task_id + '-shell', signal.command);
          return { ok: res.status === 'SUCCESS', report: res.report, exit_code: res.exit_code };
        }
        default:
          return { ok: false, error: `Signal type '${signal.type}' not supported by PeerServer` };
      }
    };

    if (cap.type === 'llm') {
      // LLM capabilities (GEMINI, CLAUDE, CODEX, HAIKU, MISTRAL) — run via TS executeTask in-process
      this.registry.update(task_id, 'running');
      const wsSender = async (ev: object) => {
        const e = ev as any;
        const inner = (e.event ?? e) as any;
        if (inner.type === 'progress') {
          this.registry.updateProgress(task_id, inner.payload?.percent ?? 0, inner.payload?.message ?? '');
        }
        this.bus.broadcast(inner);
      };
      const cmdArgs = [...(cap.args as string[]), prompt];
      try {
        const taskPromise = executeTask(task_id, capability, cmdArgs, wsSender, undefined, signalHandler);
        // Track the executeTask promise if possible, but executeTask spawns its own children
        // The most critical part is the shell capability.
        const manifest = await taskPromise;
        const ok = manifest.status === 'SUCCESS';
        
        // AAAK Hook: Post-result
        this.aaak.postResult(manifest, prompt);

        const usageForRegistry = manifest.usage ? { ...manifest.usage, cost_usd: manifest.usage.cost_usd ?? undefined } : undefined;
        this.registry.update(task_id, ok ? 'completed' : 'failed', { status: manifest.status, ok, report: manifest.report, usage: manifest.usage }, usageForRegistry);
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: manifest.status, ok, report: manifest.report, usage: manifest.usage } });
        this.logUsage('legion_ts', ok ? 'completed' : 'failed', task_id, manifest.usage);
      } catch (e: any) {
        this.registry.update(task_id, 'failed', { error: String(e) });
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: 'FAILED', ok: false, report: String(e) } });
      } finally {
        this.activeSubprocesses.delete(task_id);
      }
      return;
    }

    if (cap.type === 'shell') {
      this.registry.update(task_id, 'running');
      const wsSender = async (ev: object) => {
        const inner = (ev as any).event ?? ev;
        if (inner.type === 'progress') {
          this.registry.updateProgress(task_id, inner.payload?.percent ?? 0, inner.payload?.message ?? '');
        }
        this.bus.broadcast(inner);
      };
      try {
        const shellPromise = executeShell(task_id, prompt, wsSender);
        this.activeSubprocesses.set(task_id, { kill: () => (shellPromise as any).kill?.() });
        const result = await shellPromise;
        const ok = result.status === 'SUCCESS';

        // AAAK Hook: Post-result
        this.aaak.postResult({
          task_id,
          status: result.status,
          report: result.report
        }, prompt);

        this.registry.update(task_id, ok ? 'completed' : 'failed', { status: result.status, ok, report: result.report });
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: result.status, ok, report: result.report } });
        this.logUsage('shell_ts', ok ? 'completed' : 'failed', task_id, undefined);
      } catch (e: any) {
        this.registry.update(task_id, 'failed', { error: String(e) });
        this.bus.broadcast({ type: 'complete', task_id, payload: { status: 'FAILED', ok: false, report: String(e) } });
      } finally {
        this.activeSubprocesses.delete(task_id);
      }
      return;
    }
  }
}

import { fileURLToPath } from 'url';
if (process.argv[1] === fileURLToPath(import.meta.url)) new PeerServer(process.argv[2] || 'GEMINI', process.argv[3] ? parseInt(process.argv[3]) : undefined).start();
