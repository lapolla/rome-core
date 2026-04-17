import { WebSocketServer, WebSocket } from 'ws';
import { v4 as uuidv4 } from 'uuid';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';
import { spawn } from 'child_process';
import type { RomeMessage, TaskUsage, RomeEvent } from './rome_types.js';
import { getRomeVersion } from './rome_types.js';
import { EventBus, TaskRegistry, WorkerRegistry, Blackboard, MeshReducer } from './registry.js';
import { executeTask } from './legion_worker.js';
import { executeShell } from './shell_executor.js';
import { AAAK } from './aaak/index.js';
import { probeArsenal, type ProbeResult } from './arsenal_probe.js';

const ROME_ROOT = process.env.ROME_ROOT || process.cwd();
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
  private aaak: AAAK;
  private startTime = Date.now() / 1000;
  private activeSubprocesses = new Map<string, { kill: () => void }>();
  private tickScheduled = false;
  private arsenal: any;
  private probeResults: Record<string, ProbeResult> = {};
  private capability: string;
  private port: number;

  constructor(capability: string, port?: number) {
    this.capability = capability.toUpperCase();
    this.arsenal = loadArsenal(ROME_ROOT);
    this.aaak = new AAAK("default", { enabled: true });
    this.registry.hydrateFromLog(path.join(ROME_ROOT, 'logs', 'rome.jsonl'));
    this.blackboard.setPersistence(path.join(ROME_ROOT, 'legions', '.rome_STATE.json'));

    let meshPort = 8741;

    try {
      const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
      if (fs.existsSync(configPath)) {
        const content = fs.readFileSync(configPath, 'utf-8');
        for (const line of content.split('\n')) {
          if (line.startsWith('MESH_PORT=')) meshPort = parseInt(line.split('=')[1]);
        }
      }
    } catch {}

    this.port = port !== undefined ? port : meshPort;
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

    return new Promise((resolve, reject) => {
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
              this.workers.register(ws, p.capabilities, p.version, p.platform, p.peer_url);
              ws.send(JSON.stringify({ type: 'worker_ack', ok: true, payload: { message: 'Registered', capabilities_accepted: p.capabilities } }));
              this.scheduleTick();
            }
            else if (msg.type === 'event') this.handleWorkerEvent(ws, msg);
          } catch (e) {
            console.error('ROME Peer Server: message error:', e);
          }
        });

        const busSub = (ev: RomeEvent) => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'event', event: ev })); };
        this.bus.subscribe(busSub);
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
          this.aaak.postResult({ task_id: tid, status: p.status, report: p.report, usage: p.usage }, task?.prompt || "");
        }
        const usage = p.usage ? { ...p.usage, cost_usd: p.usage.cost_usd ?? undefined } : undefined;
        this.registry.update(tid, status, p, usage);
        this.processStateReduction(tid);
        this.bus.broadcast({ type: 'complete', task_id: tid, payload: p });
        this.workers.markIdle(ws, tid);
        this.logUsage('worker', status, tid, p.usage);
        this.scheduleTick();
        break;
      case 'error':
        this.registry.update(tid, 'failed', { error: p.message });
        this.bus.broadcast({ type: 'error', task_id: tid, payload: p });
        this.workers.markIdle(ws, tid);
        this.scheduleTick();
        break;
    }
  }

  private logUsage(tool: string, status: string, task_id: string, usage: any) {
    const logPath = path.join(ROME_ROOT, 'logs', 'rome.jsonl');
    const entry = JSON.stringify({ ts: Date.now() / 1000, tool, task_id, status, usage }) + '\n';
    fs.promises.appendFile(logPath, entry).catch(() => {});
  }

  private async handleCommand(ws: WebSocket, msg: RomeMessage) {
    const { command, request_id, payload } = msg;
    switch (command) {
      case 'ping': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { pong: true } })); break;
      case 'state_get': ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { key: payload?.key, value: this.blackboard.get(payload?.key) } })); break;
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
        
        // V7 Protocol: Shell capabilities (SAFE_SHELL, TEST, etc) bypass AAAK natural language context
        const capConfig = this.arsenal[capability];
        const distilledPrompt = (capConfig?.type === 'shell') 
          ? prompt 
          : this.aaak.preDispatch(prompt, '', capability);

        if (capability === 'NATIVE_SHELL') {
          this.registry.register(task_id, 'NATIVE_SHELL', prompt, undefined, prompt.slice(0, 50), 'Native Daemon Shell');
          this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability: 'NATIVE_SHELL' } });
          this.scheduleTick();
          this.runNativeShell(ws, request_id || '', prompt, task_id);
          ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { task_id, accepted: true, routed_to: 'native_shell' } }));
          break;
        }

        this.registry.register(task_id, capability, prompt, payload.parent_task_id, payload.goal, payload.intent);
        this.bus.broadcast({ type: 'dispatch_start', task_id, payload: { capability, goal: payload.goal, intent: payload.intent } });
        this.scheduleTick();
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
        this.scheduleTick();
        this.runNativeShell(ws, request_id || '', cmdStr, task_id);
        break;
      }
      case 'status': {
        ws.send(JSON.stringify({ type: 'response', request_id, ok: true, payload: { 
          tasks: Object.fromEntries(this.registry.getAll().map(t => [t.task_id, t])), 
          workers: this.workers.getInfo(), 
          ...this.registry.getSessionStats(), 
          uptime_s: (Date.now() / 1000) - this.startTime,
          state: this.blackboard.get()
        } }));
        break;
      }
      case 'await': {
        const tids = Array.isArray(payload.task_ids) ? payload.task_ids : [payload.task_id];
        const results = await Promise.all(tids.map((tid: string) => this.registry.awaitTask(tid, this.bus)));
        ws.send(JSON.stringify({ type: 'response', request_id, ok: results.every(r => r && ['completed', 'success'].includes(r.status.toLowerCase())), payload: { tasks: results.filter(r => r !== null) } }));
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
      case 'reset': this.registry.clearAll(); this.bus.broadcast({ type: 'reset', task_id: '', payload: { cleared: true } }); ws.send(JSON.stringify({ type: 'response', request_id, ok: true })); break;
      default: ws.send(JSON.stringify({ type: 'response', request_id, ok: false, error: `Unknown command: ${command}` }));
    }
  }

  private runNativeShell(ws: WebSocket, request_id: string, command: string, taskId?: string) {
    const proc = spawn('/bin/bash', ['-c', command], { cwd: ROME_ROOT, env: { ...process.env, FORCE_COLOR: '1' }, detached: true });
    let output = '';
    proc.stdout.on('data', (d) => output += d.toString());
    proc.stderr.on('data', (d) => output += d.toString());
    proc.on('close', (code) => {
      ws.send(JSON.stringify({ type: 'response', request_id, ok: code === 0, payload: { output, code } }));
      if (taskId) {
        this.registry.update(taskId, code === 0 ? 'completed' : 'failed', { report: output });
        this.bus.broadcast({ type: 'complete', task_id: taskId, payload: { status: code === 0 ? 'SUCCESS' : 'FAILED', report: output } });
        this.scheduleTick();
      }
    });
    if (taskId) this.activeSubprocesses.set(taskId, { kill: () => process.kill(-proc.pid!) });
  }

  private runLegion(task_id: string, capability: string, prompt: string) {
    const wsSender = async (ev: any) => this.bus.broadcast({ ...ev, task_id });
    const cap = this.arsenal[capability];
    if (!cap) {
      this.registry.update(task_id, 'failed', { error: `Unknown capability: ${capability}` });
      this.bus.broadcast({ type: 'error', task_id, payload: { message: `Unknown capability: ${capability}` } });
      return;
    }
    if (cap.type === 'shell') {
      executeShell(task_id, prompt, wsSender).then(res => {
        this.registry.update(task_id, res.status === 'SUCCESS' ? 'completed' : 'failed', res);
        this.bus.broadcast({ type: 'complete', task_id, payload: res });
        this.logUsage('shell', res.status, task_id, null);
        this.scheduleTick();
      });
    } else {
      const model = cap.model || 'gemini-3.1-pro-preview';
      const effectivePrompt = cap.system_prompt ? `${cap.system_prompt}\n\nTASK: ${prompt}` : prompt;
      const finalArgs = (cap.args || []).map((a: any) => typeof a === 'string' ? a.replace(/{MODEL}/g, model) : a).concat(effectivePrompt);
      executeTask(task_id, capability, finalArgs, wsSender).then(manifest => {
        const usage = manifest.usage ? { ...manifest.usage, cost_usd: manifest.usage.cost_usd ?? undefined } : undefined;
        this.registry.update(task_id, manifest.status === 'SUCCESS' ? 'completed' : 'failed', manifest, usage);
        this.bus.broadcast({ type: 'complete', task_id, payload: manifest });
        this.logUsage('legion', manifest.status, task_id, manifest.usage);
        this.scheduleTick();
      }).catch(e => {
        this.registry.update(task_id, 'failed', { error: e.message });
        this.bus.broadcast({ type: 'error', task_id, payload: { message: e.message } });
        this.scheduleTick();
      });
    }
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
    // Reap zombie tasks (running > 180s)
    for (const t of this.registry.getAll()) {
      if (t.status === 'running' && (Date.now() / 1000) - t.ts > 180) {
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
