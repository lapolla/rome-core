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
  updated_at?: number;
  result?: any;
  usage?: TaskUsage;
  parent_task_id?: string | undefined;
  dispatch_mode?: 'subprocess' | 'peer_forward' | 'persistent_worker' | undefined;
  peer_url?: string | undefined;
  progress_percent?: number | undefined;
  progress_message?: string | undefined;
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
  peer_url: string;
}
