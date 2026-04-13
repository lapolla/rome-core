import * as fs from 'fs';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { WebSocket } from 'ws';
import { executeTask } from './legion_worker.js';
import { executeShell } from './shell_executor.js';

const ROME_ROOT = process.env.ROME_ROOT || process.cwd();
let WS_URL = process.env.ROME_WS_URL;
let TOKEN = process.env.ROME_WS_TOKEN;

const configPath = path.join(ROME_ROOT, 'dictator', 'config.json');
if (fs.existsSync(configPath)) {
  try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    if (!WS_URL && config.mesh_port) {
      WS_URL = `ws://127.0.0.1:${config.mesh_port}/ws`;
    }
    if (!TOKEN && config.sovereign_token_path) {
      const tokenPath = path.join(ROME_ROOT, config.sovereign_token_path);
      if (fs.existsSync(tokenPath)) {
        TOKEN = fs.readFileSync(tokenPath, 'utf-8').trim();
      }
    }
  } catch (e) {
    console.error('Error reading config.json:', e);
  }
}

if (!WS_URL) throw new Error("Mesh URL not configured (no ROME_WS_URL or dictator/config.json)");
if (!TOKEN) throw new Error("Mesh Token not configured");

function loadArsenal() {
  const arsenalPath = path.join(ROME_ROOT, 'arsenal', 'core_arsenal.json');
  if (!fs.existsSync(arsenalPath)) return {};
  const raw = JSON.parse(fs.readFileSync(arsenalPath, 'utf-8'));
  const geminiCli = process.env.GEMINI_CLI || path.join(process.env.HOME || '', 'projects/gemini-cli/bundle/gemini.js');

  const resolve = (val: any): any => {
    if (typeof val === 'string') return val.replace(/{ROME_ROOT}/g, ROME_ROOT).replace(/{GEMINI_CLI}/g, geminiCli);
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

async function runViaMesh(capability: string, prompt: string): Promise<boolean> {
  return new Promise((resolve) => {
    const ws = new WebSocket(`${WS_URL!}${WS_URL!.includes('?') ? '&' : '?'}token=${TOKEN}`);
    let taskId: string;

    ws.on('open', () => {
      ws.send(JSON.stringify({
        type: 'command',
        command: 'dispatch',
        request_id: 'cli-' + Date.now(),
        payload: { capability, prompt, goal: prompt.slice(0, 50), intent: "CLI Dispatch" }
      }));
    });

    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'response' && msg.ok) {
        taskId = msg.payload.task_id;
        console.log(`[MESH] Dispatched task ${taskId} (Routed to: ${msg.payload.routed_to})`);
      } else if (msg.type === 'event' && msg.event.task_id === taskId) {
        const ev = msg.event;
        if (ev.type === 'progress') {
          process.stdout.write(`\r[${taskId}] ${ev.payload.percent}% >> ${ev.payload.message}`.padEnd(80));
        } else if (ev.type === 'complete') {
          console.log(`\n[${taskId}] COMPLETE: ${ev.payload.status}`);
          if (ev.payload.report) {
            console.log("--- REPORT ---");
            console.log(ev.payload.report);
            console.log("--------------");
          }
          // Do not close WS - keep the pipe open for mesh persistence
          resolve(true);
        }
      }
    });

    ws.on('error', () => resolve(false));
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.log("Usage: node dist/client.js <capability> <prompt>");
    process.exit(1);
  }

  const capabilityName = args[0].toUpperCase();
  const prompt = args[1];

  // Try mesh first
  const meshSuccess = await runViaMesh(capabilityName, prompt);
  if (meshSuccess) process.exit(0);

  // Fallback to detached
  console.log(`[ROME] Mesh unavailable. Falling back to detached execution.`);
  const arsenal = loadArsenal();
  const cap = arsenal[capabilityName];
  if (!cap) { console.error(`Unknown capability: ${capabilityName}`); process.exit(1); }

  const taskId = `ts-${uuidv4().substring(0, 8)}`;
  const wsSender = async (ev: any) => {
    const inner = ev.event ?? ev;
    if (inner.type === 'progress') {
      process.stdout.write(`\r[${taskId}] ${inner.payload?.percent ?? 0}% >> ${inner.payload?.message ?? ''}`.padEnd(80));
    }
  };

  if (cap.type === 'shell' || capabilityName === 'SAFE_SHELL') {
    const res = await executeShell(taskId, prompt, wsSender);
    console.log(`\n[${taskId}] COMPLETE: ${res.status}\n--- REPORT ---\n${res.report}\n--------------`);
    process.exit(res.status === 'SUCCESS' ? 0 : 1);
  } else if (cap.type === 'llm') {
    const model = cap.model || 'gemini-3.1-pro-preview';
    const finalArgs = (cap.args || []).map((a: any) => typeof a === 'string' ? a.replace(/{MODEL}/g, model) : a).concat(prompt);
    const manifest = await executeTask(taskId, capabilityName, finalArgs, wsSender);
    console.log(`\n[${taskId}] COMPLETE: ${manifest.status}\n--- REPORT ---\n${manifest.report}\n--------------`);
    process.exit(manifest.status === 'SUCCESS' ? 0 : 1);
  }
}

main().catch(console.error);
