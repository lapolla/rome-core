import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export function getRomeVersion(): string {
  try {
    return execSync('git describe --tags --always --dirty', { stdio: 'pipe' }).toString().trim();
  } catch {
    try {
      const pkg = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'package.json'), 'utf-8'));
      return pkg.version || '0.0.0-unknown';
    } catch {
      return '0.0.0-unknown';
    }
  }
}

export interface RomeMessage {
  type: string;
  request_id?: string;
  command?: string;
  payload?: any;
  ok?: boolean;
  error?: string;
  event?: any;
}

export interface TaskInfo {
  task_id: string;
  capability: string;
  prompt: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  ts: number;
  created_at?: number;
  updated_at?: number;
  completed_at?: number;
  result?: any;
  usage?: TaskUsage;
  parent_task_id?: string | undefined;
  dispatch_mode?: 'subprocess' | 'peer_forward' | 'persistent_worker' | undefined;
  progress_percent?: number | undefined;
  progress_message?: string | undefined;
  goal?: string | undefined;
  intent?: string | undefined;
  report?: string | undefined;

}

export interface TaskUsage {
  total_tokens: number;
  prompt_tokens?: number | undefined;
  completion_tokens?: number | undefined;
  cost_usd?: number | undefined;
  model?: string | undefined;
}

export interface RomeEvent {
  type: string;
  task_id: string;
  ts: number;
  payload: any;
  sequence?: number | undefined;
  source?: string | undefined;
}

export interface PeerInfo {
  worker_id: string;
  capabilities: string[];
  busy_tasks: string[];
  connected_at: number;
  version: string;
  platform: string;
  one_shot?: boolean;
}

/* ── Decomposer types (v1) ───────────────────────────────────────────────── */

export type WorkerRole = 'GEMMA' | 'CLAUDE' | 'GEMINI' | 'MISTRAL' | 'SAFE_SHELL' | 'NATIVE_SHELL';
export type ExecutionMode = 'native_ws' | 'cli' | 'fallback';

export interface DecompTask {
  id: string;
  prompt: string;
  context?: object;
}

export interface DecompStep {
  id: string;
  dependsOn?: string[];
  payload: {
    role: WorkerRole;
    mode: ExecutionMode;
    input: string;
  };
}

export interface Plan {
  taskId: string;
  steps: DecompStep[];
}
