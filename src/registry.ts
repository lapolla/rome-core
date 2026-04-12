import { WebSocket } from 'ws';
import type { TaskInfo, RomeEvent, TaskUsage, PeerInfo } from './rome_types.js';
import { EventEmitter } from 'events';

export class EventBus {
  private subscribers: Set<WebSocket> = new Set();
  private eventHistory: RomeEvent[] = [];
  private sequence = 0;

  subscribe(ws: WebSocket) {
    this.subscribers.add(ws);
  }

  unsubscribe(ws: WebSocket) {
    this.subscribers.delete(ws);
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
    for (const ws of this.subscribers) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(msg);
      }
    }
  }

  getRecent(limit: number = 10): RomeEvent[] {
    return this.eventHistory.slice(-limit);
  }
}

export class TaskRegistry {
  private tasks: Map<string, TaskInfo & { emitter: EventEmitter }> = new Map();
  private sessionUsage: TaskUsage = { total_tokens: 0, cost_usd: 0 };

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
    };
  }

  addUsage(tokens: number, cost_usd: number) {
    this.sessionUsage.total_tokens += tokens;
    this.sessionUsage.cost_usd = (this.sessionUsage.cost_usd || 0) + cost_usd;
  }

  clearFinished() {
    for (const [id, task] of this.tasks.entries()) {
      if (['completed', 'failed', 'cancelled'].includes(task.status)) this.tasks.delete(id);
    }
  }

  clearAll() {
    this.tasks.clear();
  }

  async awaitTask(task_id: string, timeoutMs: number = 300000): Promise<TaskInfo | null> {
    const task = this.tasks.get(task_id);
    if (!task) return null;
    if (['completed', 'failed', 'cancelled'].includes(task.status)) return task;

    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        task.emitter.removeListener('done', onDone);
        resolve(this.get(task_id) || null);
      }, timeoutMs);

      const onDone = (t: TaskInfo) => {
        clearTimeout(timer);
        resolve(t);
      };

      task.emitter.once('done', onDone);
    });
  }
}

export class WorkerRegistry {
  private workers: Map<WebSocket, PeerInfo> = new Map();

  register(ws: WebSocket, caps: string[], version: string = "", platform: string = "", peer_url: string = "") {
    this.workers.set(ws, {
      worker_id: Math.random().toString(36).substring(7),
      capabilities: caps.map(c => c.toUpperCase()),
      busy_tasks: [],
      connected_at: Date.now() / 1000,
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
    if (entry) entry.busy_tasks.push(task_id);
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

  count(): number {
    return this.workers.size;
  }
}
