import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';
import { randomUUID } from 'crypto';

/**
 * ROME NATIVE AGENT (v7.1.0)
 * Pure JS/TS implementation with FULL DUPLEX WS comms and Real-time Tool Use.
 */

interface AgentConfig {
  wsUrl: string;
  token: string;
  capability: string;
  model: string;
  ollamaUrl?: string;
  mistralKey?: string;
  cliCommand?: string;
  cliOutputFormat?: 'json' | 'text';
}

export class MeshAgent {
  private ws: WebSocket | null = null;
  private config: AgentConfig;
  private workerId: string = Math.random().toString(36).substring(7);
  private pendingRequests = new Map<string, (msg: any) => void>();

  constructor(config: AgentConfig) {
    this.config = config;
  }

  private _disconnecting = false;
  private _reconnectTimer: NodeJS.Timeout | null = null;

  disconnect() {
    this._disconnecting = true;
    if (this._reconnectTimer) clearTimeout(this._reconnectTimer);
    this.ws?.close();
  }

  async connect() {
    const url = `${this.config.wsUrl}${this.config.wsUrl.includes('?') ? '&' : '?'}token=${this.config.token}`;
    this.ws = new WebSocket(url);

    this.ws.on('open', () => {
      console.log(`[${this.config.capability}] Connected to Mesh: ${this.config.wsUrl}`);
      this.send({
        type: 'agent_hello',
        payload: {
          capabilities: [this.config.capability],
          one_shot: false,
          version: '7.1.0-native',
          platform: process.platform,
          worker_id: this.workerId
        }
      });
    });

    this.ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        
        // Handle responses to our commands (Full Duplex)
        if (msg.type === 'response' && msg.request_id && this.pendingRequests.has(msg.request_id)) {
          const resolve = this.pendingRequests.get(msg.request_id)!;
          this.pendingRequests.delete(msg.request_id);
          resolve(msg);
          return;
        }

        // Handle events for our commands
        if (msg.type === 'event' && msg.event?.type === 'complete' && this.pendingRequests.has(`event-${msg.event.task_id}`)) {
          const resolve = this.pendingRequests.get(`event-${msg.event.task_id}`)!;
          this.pendingRequests.delete(`event-${msg.event.task_id}`);
          resolve(msg.event);
          return;
        }

        // Handle incoming tasks
        if (msg.type === 'command' && msg.command === 'dispatch' && msg.payload.capability === this.config.capability) {
          this.handleDispatch(msg);
        }
      } catch (e) {
        console.error('WS Message Error:', e);
      }
    });

    this.ws.on('close', () => {
      console.log(`[${this.config.capability}] Disconnected. Reconnecting...`);
      if (!this._disconnecting) this._reconnectTimer = setTimeout(() => this.connect(), 2000);
    });
  }

  private send(obj: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  private async request(command: string, payload: any): Promise<any> {
    const requestId = `native-${randomUUID().substring(0, 8)}`;
    return new Promise((resolve) => {
      this.pendingRequests.set(requestId, resolve);
      this.send({ type: 'command', command, request_id: requestId, payload });
      // Timeout guard
      setTimeout(() => { if (this.pendingRequests.has(requestId)) { this.pendingRequests.delete(requestId); resolve({ ok: false, error: 'timeout' }); } }, 30000);
    });
  }

  private async awaitTask(taskId: string): Promise<any> {
    return new Promise((resolve) => {
      this.pendingRequests.set(`event-${taskId}`, resolve);
      // Long timeout for subtasks
      setTimeout(() => { if (this.pendingRequests.has(`event-${taskId}`)) { this.pendingRequests.delete(`event-${taskId}`); resolve({ status: 'FAILED', report: 'Subtask timeout' }); } }, 300000);
    });
  }

  private async handleDispatch(msg: any) {
    const { task_id, prompt } = msg.payload;
    const logPath = '/tmp/rome-native-debug.log';
    fs.appendFileSync(logPath, `\n\n--- TASK ${task_id} ---\nPROMPT: ${prompt}\n`);

    console.log(`[${this.config.capability}] Task engaged: ${task_id}`);
    this.send({ type: 'response', request_id: msg.request_id, ok: true });

    const systemPrompt = `You are a ROME Native Agent (v7). You have direct mesh access.
To execute shell commands, emit: [ROME_SHELL: "command"]
Always use this exact format. When you receive a result, analyze it and continue or finish.`;

    const messages = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: prompt }
    ];
    let turns = 0;
    const MAX_TURNS = 10;

    try {
      while (turns < MAX_TURNS) {
        turns++;
        this.sendEvent(task_id, 'progress', { percent: Math.min(90, turns * 10), message: `Thinking (Turn ${turns})...` });
        
        const responseText = await this.callLLM(messages);
        fs.appendFileSync(logPath, `TURN ${turns} RESPONSE:\n${responseText}\n`);
        
        messages.push({ role: 'assistant', content: responseText });

        const signals = this.parseSignals(responseText);
        fs.appendFileSync(logPath, `PARSED SIGNALS: ${JSON.stringify(signals)}\n`);
        
        if (signals.length === 0) {
          this.sendEvent(task_id, 'complete', { status: 'SUCCESS', report: responseText });
          return;
        }

        // Execute signals in sequence and feed results back
        let feedback = '';
        for (const sig of signals) {
          console.log(`[${this.config.capability}] Executing signal: ${sig.type}`);
          if (sig.type === 'shell' && sig.command) {
            const resp = await this.request('native_shell', { command: sig.command });
            const event = await this.awaitTask(resp.payload.task_id);
            feedback += `\n[SHELL RESULT: ${sig.command}]\n${event.payload.report}\n`;
          } else if (sig.type === 'dispatch' && sig.capability) {
            const resp = await this.request('dispatch', { capability: sig.capability, prompt: sig.prompt });
            const event = await this.awaitTask(resp.payload.task_id);
            feedback += `\n[DISPATCH RESULT: ${sig.capability}]\n${event.payload.report}\n`;
          }
        }
        messages.push({ role: 'user', content: feedback });
      }
      this.sendEvent(task_id, 'complete', { status: 'FAILED', report: 'Turn limit exceeded' });
    } catch (e: any) {
      this.sendEvent(task_id, 'complete', { status: 'FAILED', report: e.message });
    }
  }

  parseSignals(text: string) {
    const signals: Array<{ type: string; command?: string; capability?: string; prompt?: string }> = [];
    
    // [ROME_SHELL: "ls -la"]
    const shellRe = /\[ROME_SHELL:\s*\"([^"]+)\"\]/g;
    let m;
    while ((m = shellRe.exec(text)) !== null) {
      signals.push({ type: 'shell', command: m[1] });
    }

    // [ROME_DISPATCH: CAP "PROMPT"]
    const dispRe = /\[ROME_DISPATCH:\s*([A-Z0-9_]+)\s*\"([^"]+)\"\]/g;
    while ((m = dispRe.exec(text)) !== null) {
      signals.push({ type: 'dispatch', capability: m[1], prompt: m[2] });
    }

    // Support for Gemma's hallucinated tool format too
    if (signals.length === 0 && text.includes('<execute_bash>')) {
        const bashM = text.match(/<execute_bash>([\s\S]+?)<\/execute_bash>/);
        if (bashM) signals.push({ type: 'shell', command: bashM[1].trim() });
    }

    // Support for standard markdown bash blocks if no other signals found
    if (signals.length === 0 && text.includes('```bash')) {
        const bashM = text.match(/```bash\s*([\s\S]+?)```/);
        if (bashM) signals.push({ type: 'shell', command: bashM[1].trim() });
    }

    return signals;
  }

  private sendEvent(task_id: string, type: string, payload: any) {
    this.send({
      type: 'event',
      event: { type, task_id, payload, ts: Date.now() / 1000 }
    });
  }


  private async callCLI(messages: any[]): Promise<string> {
    const { spawn } = await import('child_process');
    const parts: string[] = [];
    for (const m of messages) {
      if (m.role === 'system') continue;
      parts.push(m.content);
    }
    const prompt = parts.join('\n\n');
    let rawCmd = (this.config.cliCommand || '').replace('{MODEL}', this.config.model || '');
    const hasPromptPlaceholder = rawCmd.includes('{PROMPT}');
    if (hasPromptPlaceholder) {
      const escaped = prompt.replace(/'/g, "'\\\\''" );
      rawCmd = rawCmd.replace('{PROMPT}', `'${escaped}'`);
    }
    return new Promise((resolve, reject) => {
      const child = spawn(rawCmd, [], { stdio: ['pipe', 'pipe', 'pipe'], shell: true, env: process.env as any });
      const chunks: Buffer[] = [];
      child.stdout!.on('data', (d: Buffer) => chunks.push(d));
      child.on('close', () => {
        const raw = Buffer.concat(chunks).toString().trim();
        if (this.config.cliOutputFormat === 'json') {
          /* try full document first (pretty-printed output), then line-by-line (NDJSON) */
          const candidates = [raw, ...raw.split('\n')];
          for (const chunk of candidates) {
            try {
              const obj = JSON.parse(chunk);
              if (obj.response) { resolve(obj.response); return; }
              if (obj.result)   { resolve(obj.result);   return; }
              if (obj.text)     { resolve(obj.text);     return; }
              if (obj.content)  { resolve(typeof obj.content === 'string' ? obj.content : JSON.stringify(obj.content)); return; }
            } catch { /* skip */ }
          }
        }
        resolve(raw);
      });
      if (!hasPromptPlaceholder) { child.stdin!.write(prompt); }
      child.stdin!.end();
      child.on('error', reject);
    });
  }

  private async callLLM(messages: any[]): Promise<string> {
    if (this.config.cliCommand) {
      return this.callCLI(messages);
    }
    if (this.config.capability === 'GEMMA') {
      return this.callOllama(messages);
    }
    return 'Driver not implemented';
  }

  private async callOllama(messages: any[]): Promise<string> {
    const url = `${this.config.ollamaUrl || 'http://localhost:11434'}/api/chat`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: this.config.model,
        messages: messages,
        stream: false,
        options: { temperature: 0 }
      })
    });
    const data = await res.json() as any;
    return data.message?.content || 'No response from Ollama';
  }
}

// ── CLI ENTRY ──────────────────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);
  const config: AgentConfig = {
    wsUrl: process.env.ROME_WS_URL || 'ws://127.0.0.1:8741/ws',
    token: process.env.ROME_WS_TOKEN || '',
    capability: process.env.ROME_CAPABILITY || 'GEMMA',
    model: process.env.ROME_MODEL || 'gemma4:e4b',
    ollamaUrl: process.env.OLLAMA_URL || 'http://localhost:11434'
  };

  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--capability') config.capability = argv[++i];
    if (argv[i] === '--model') config.model = argv[++i];
    if (argv[i] === '--ws-url') config.wsUrl = argv[++i];
    if (argv[i] === '--ws-token') config.token = argv[++i];
    if (argv[i] === '--cli') config.cliCommand = argv[++i];
    if (argv[i] === '--cli-output-format') config.cliOutputFormat = argv[++i] as 'json' | 'text';
  }

  if (!config.token) {
    const tokenPath = path.join(process.cwd(), '.rome_SOVEREIGN_TOKEN');
    if (fs.existsSync(tokenPath)) config.token = fs.readFileSync(tokenPath, 'utf-8').trim();
  }

  const agent = new MeshAgent(config);
  await agent.connect();
}

import { fileURLToPath } from 'url';
const isEntryPoint = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isEntryPoint) main().catch(console.error);
