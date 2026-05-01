import { WebSocket } from 'ws';
import type { TaskInfo, RomeEvent, TaskUsage, PeerInfo } from './rome_types.js';
import { EventEmitter } from 'events';
import * as fs from 'fs';
import * as path from 'path';

export class EventBus {
  private subscribers: Set<WebSocket | ((ev: RomeEvent) => void)> = new Set();
  private eventHistory: RomeEvent[] = [];
  private sequence = 0;

  subscribe(sub: WebSocket | ((ev: RomeEvent) => void)) {
    this.subscribers.add(sub);
    // Replay history to new subscriber
    for (const ev of this.eventHistory) {
      if (typeof sub === 'function') {
        sub(ev);
      } else if (sub.readyState === WebSocket.OPEN) {
        sub.send(JSON.stringify({ type: 'event', event: ev }));
      }
    }
  }

  unsubscribe(sub: WebSocket | ((ev: RomeEvent) => void)) {
    this.subscribers.delete(sub);
  }

  broadcast(event: Omit<RomeEvent, 'ts' | 'sequence'>) {
    const fullEvent: RomeEvent = {
      ...event,
      ts: Date.now() / 1000,
      sequence: ++this.sequence
    };
    
    this.eventHistory.push(fullEvent);
    if (this.eventHistory.length > 100) this.eventHistory.shift();

    const msg = JSON.stringify({ type: 'event', event: fullEvent });
    for (const sub of this.subscribers) {
      try {
        if (typeof sub === 'function') {
          sub(fullEvent);
        } else if (sub.readyState === WebSocket.OPEN) {
          sub.send(msg);
        }
      } catch { /* dead subscriber — ignore */ }
    }
  }

  getRecent(limit: number = 10): RomeEvent[] {
    return this.eventHistory.slice(-limit);
  }
}

export class TaskRegistry {
  private tasks: Map<string, TaskInfo & { emitter: EventEmitter }> = new Map();
  private sessionUsage: TaskUsage = { total_tokens: 0, cost_usd: 0 };
  private projectUsage: TaskUsage = { total_tokens: 0, cost_usd: 0 };

  hydrateFromLog(logPath: string) {
    if (!fs.existsSync(logPath)) return;
    try {
      const content = fs.readFileSync(logPath, 'utf-8');
      const lines = content.trim().split('\n');
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          if (entry.usage) {
            this.projectUsage.total_tokens += (entry.usage.total_tokens || 0);
            this.projectUsage.cost_usd += (entry.usage.cost_usd || 0);
          }
        } catch (e) { /* skip malformed line */ }
      }
    } catch (e) { console.error(`[Registry] Hydration failed: ${e}`); }
  }

  register(task_id: string, capability: string, prompt: string, parent_task_id?: string, goal?: string, intent?: string) {
    const now = Date.now() / 1000;
    const task: TaskInfo & { emitter: EventEmitter } = {
      task_id,
      capability,
      prompt,
      status: 'pending',
      ts: now,
      created_at: now,
      updated_at: now,
      parent_task_id,
      goal: goal || prompt.slice(0, 50),
      intent: intent || 'Autonomous Execution',
      emitter: new EventEmitter()
    };
    this.tasks.set(task_id, task);
  }

  update(task_id: string, status: TaskInfo['status'], result?: any, usage?: TaskUsage) {
    const task = this.tasks.get(task_id);
    if (task) {
      task.status = status;
      task.updated_at = Date.now() / 1000;
      if (result !== undefined) {
        task.result = result;
        if (result.report) task.report = result.report;
      }
      if (['completed', 'failed', 'cancelled'].includes(status) && !task.completed_at) {
        task.completed_at = Date.now() / 1000;
        if (status === 'completed') task.progress_percent = 100;
      }
      if (usage) {
        task.usage = usage;
        this.sessionUsage.total_tokens += usage.total_tokens;
        this.sessionUsage.cost_usd = (this.sessionUsage.cost_usd || 0) + (usage.cost_usd || 0);
        this.projectUsage.total_tokens += usage.total_tokens;
        this.projectUsage.cost_usd = (this.projectUsage.cost_usd || 0) + (usage.cost_usd || 0);
      }
      if (['completed', 'failed', 'cancelled'].includes(status)) {
        task.emitter.emit('done', task);
      }
    }
  }

  updateProgress(task_id: string, percent: number, message: string) {
    const task = this.tasks.get(task_id);
    if (task) {
      task.progress_percent = percent;
      task.progress_message = message;
      task.updated_at = Date.now() / 1000;
    }
  }

  get(task_id: string): TaskInfo | undefined {
    const task = this.tasks.get(task_id);
    if (!task) return undefined;
    const { emitter, ...info } = task;
    return info;
  }

  getAll(): TaskInfo[] {
    return Array.from(this.tasks.values()).map(({ emitter, ...info }) => info);
  }

  getUsage(): TaskUsage {
    return this.sessionUsage;
  }

  getSessionStats() {
    return {
      session_worker_tokens: this.sessionUsage.total_tokens,
      session_cost_usd: this.sessionUsage.cost_usd || 0,
      project_total_tokens: this.projectUsage.total_tokens,
      project_total_cost_usd: this.projectUsage.cost_usd || 0,
    };
  }

  addUsage(tokens: number, cost_usd: number) {
    this.sessionUsage.total_tokens += tokens;
    this.sessionUsage.cost_usd = (this.sessionUsage.cost_usd || 0) + cost_usd;
    this.projectUsage.total_tokens += tokens;
    this.projectUsage.cost_usd = (this.projectUsage.cost_usd || 0) + cost_usd;
  }

  clearFinished() {
    for (const [id, task] of this.tasks.entries()) {
      if (['completed', 'failed', 'cancelled'].includes(task.status)) this.tasks.delete(id);
    }
  }

  clearAll() {
    this.tasks.clear();
  }

}

export class WorkerRegistry {
  private workers: Map<WebSocket, PeerInfo> = new Map();

  register(ws: WebSocket, caps: string[], version: string = "", platform: string = "", peer_url: string = "", one_shot: boolean = true) {
    this.workers.set(ws, {
      worker_id: Math.random().toString(36).substring(7),
      capabilities: (caps || []).map(c => c.toUpperCase()),
      busy_tasks: [],
      connected_at: Date.now() / 1000,
      one_shot,
      version,
      platform,
      peer_url
    });
  }

  unregister(ws: WebSocket): string[] {
    const entry = this.workers.get(ws);
    const orphaned = entry ? entry.busy_tasks : [];
    this.workers.delete(ws);
    return orphaned;
  }

  findWorker(capability: string): WebSocket | null {
    const cap = capability.toUpperCase();
    for (const [ws, entry] of this.workers.entries()) {
      if (entry.capabilities.includes(cap) && entry.busy_tasks.length === 0) {
        return ws;
      }
    }
    return null;
  }

  findWorkerByTask(task_id: string): WebSocket | null {
    for (const [ws, entry] of this.workers.entries()) {
      if (entry.busy_tasks.includes(task_id)) {
        return ws;
      }
    }
    return null;
  }

  markBusy(ws: WebSocket, task_id: string) {
    const entry = this.workers.get(ws);
    if (entry && !entry.busy_tasks.includes(task_id)) entry.busy_tasks.push(task_id);
  }

  markIdle(ws: WebSocket, task_id: string) {
    const entry = this.workers.get(ws);
    if (entry) {
      entry.busy_tasks = entry.busy_tasks.filter(tid => tid !== task_id);
    }
  }

  getInfo(): PeerInfo[] {
    return Array.from(this.workers.values());
  }

  isOneShot(ws: WebSocket): boolean {
    const entry = this.workers.get(ws);
    return (entry?.one_shot !== false) && (entry?.busy_tasks.length === 0);
  }

  count(): number {
    return this.workers.size;
  }
}

export interface StateUpdate {
  key: string;
  value: any;
  caused_by_task: string;
  task_ts: number;
}

export class Blackboard {
  private state: Record<string, any> = {};
  private causalMeta: Record<string, { caused_by_task: string, task_ts: number }> = {};
  private persistencePath: string | null = null;

  setPersistence(path: string) {
    this.persistencePath = path;
    this.hydrate();
  }

  hydrate() {
    if (!this.persistencePath || !fs.existsSync(this.persistencePath)) return;
    try {
      const data = JSON.parse(fs.readFileSync(this.persistencePath, 'utf-8'));
      if (data.state) this.state = data.state;
      if (data.causalMeta) this.causalMeta = data.causalMeta;
    } catch (e) { console.error(`[Blackboard] Hydration failed: ${e}`); }
  }

  save() {
    if (!this.persistencePath) return;
    try {
      const dir = path.dirname(this.persistencePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(this.persistencePath, JSON.stringify({
        state: this.state,
        causalMeta: this.causalMeta,
        updated_at: Date.now() / 1000
      }, null, 2));
    } catch (e) { console.error(`[Blackboard] Save failed: ${e}`); }
  }

  get(key?: string) {
    if (key) return this.state[key];
    return this.state;
  }

  getMeta(key: string) {
    return this.causalMeta[key];
  }

  delete(key: string): boolean {
    if (!(key in this.state)) return false;
    delete this.state[key];
    delete this.causalMeta[key];
    this.save();
    return true;
  }

  set(update: StateUpdate): boolean {
    const existingMeta = this.causalMeta[update.key];
    // Optimistic concurrency: reject updates from older tasks if a newer task updated it
    if (existingMeta && existingMeta.task_ts > update.task_ts) {
      return false; // Rejected
    }
    
    // Atomic patching: shallow merge if both are objects, otherwise replace
    if (typeof this.state[update.key] === 'object' && this.state[update.key] !== null &&
        typeof update.value === 'object' && update.value !== null && !Array.isArray(update.value)) {
      this.state[update.key] = { ...this.state[update.key], ...update.value };
    } else {
      this.state[update.key] = update.value;
    }

    this.causalMeta[update.key] = {
      caused_by_task: update.caused_by_task,
      task_ts: update.task_ts
    };
    this.save();
    return true;
  }
}

export class MeshReducer {
  reduce(task: TaskInfo): StateUpdate | null {
    const report = (task.report || '').toLowerCase();
    const cap = (task.capability || '').toUpperCase();
    const prompt = (task.prompt || '').toLowerCase();
    const status = (task.status || '').toLowerCase();

    // Deterministic Pattern: Build & Test Status
    if (cap === 'TEST' || (cap === 'SAFE_SHELL' && (prompt.includes('test') || prompt.includes('tsc')))) {
      const hasActualFailures = /# fail\s+[1-9]/i.test(report) || report.includes('err_test_failure') || report.includes('failed');
      const val = {
        status: (status === 'failed' || hasActualFailures || report.includes('error:')) ? 'FAILED' : 'SUCCESS',
        ts: task.ts,
        task_id: task.task_id,
        goal: task.goal
      };
      return { key: 'build_status', value: val, caused_by_task: task.task_id, task_ts: task.ts };
    }

    // Deterministic Pattern: Linting
    if (prompt.includes('lint') || prompt.includes('eslint')) {
      const val = {
        status: (status === 'failed' || report.includes('error')) ? 'DIRTY' : 'CLEAN',
        ts: task.ts,
        task_id: task.task_id,
        goal: task.goal
      };
      return { key: 'lint_status', value: val, caused_by_task: task.task_id, task_ts: task.ts };
    }

    return null;
  }
}
