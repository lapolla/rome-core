/**
 * ROME Bootstrap — pure worker spawner.
 * Reads dictator/workers.json, probes each worker, spawns survivors.
 * No routing logic here. Policy owns the truth.
 */
import { execSync, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import WebSocket from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROME_ROOT = process.env.ROME_ROOT || path.resolve(__dirname, '../..');

interface WorkerPolicy {
  capability: string;
  invocation: 'direct_ws' | 'native_agent_cli' | 'native_agent_ollama';
  probe: string;
  start_command?: string;
  cli_command?: string;
  output_format?: 'json' | 'text';
  model?: string;
  ollama_url?: string;
}

interface SpawnResult {
  capability: string;
  status: 'spawned' | 'skipped';
  pid: number | null;
}

function probe(cmd: string, env: Record<string, string>): boolean {
  try {
    execSync(cmd, { env: { ...process.env, ...env }, stdio: 'ignore', timeout: 3000 });
    return true;
  } catch { return false; }
}

function spawnWorker(w: WorkerPolicy, wsUrl: string, env: Record<string, string>): number | null {
  const logPath = `/tmp/rome-worker-${w.capability}.log`;
  const combinedEnv = { ...process.env, ...env };

  if (w.invocation === 'direct_ws') {
    /* Native WS peer — spawns and self-registers with daemon via agent_hello */
    const cmd = (w.start_command || '')
      .replace(/\$GEMINI_CLI/g, combinedEnv.GEMINI_CLI || '')
      .replace(/\$ROME_ROOT/g, ROME_ROOT);
    const [bin, ...cmdArgs] = cmd.split(' ');
    const child = spawn(bin, cmdArgs, {
      detached: true,
      stdio: ['ignore', fs.openSync(logPath, 'w'), fs.openSync(logPath, 'a')],
      env: { ...combinedEnv, ROME_DAEMON_URL: `${wsUrl}/ws` },
      shell: true,
    });
    child.unref();
    console.log(`  [+] ${w.capability} spawned (pid ${child.pid}, direct_ws)`);
    return child.pid || null;
  }

  let args: string[];
  if (w.invocation === 'native_agent_ollama') {
    args = [
      path.join(ROME_ROOT, 'dist/src/native_agent.js'),
      '--capability', w.capability,
      '--model', w.model || '',
      '--ws-url', `${wsUrl}/ws`,
    ];
  } else {
    const cli = (w.cli_command || '')
      .replace(/\$GEMINI_CLI/g, combinedEnv.GEMINI_CLI || '')
      .replace(/\$ROME_ROOT/g, ROME_ROOT);
    args = [
      path.join(ROME_ROOT, 'dist/src/native_agent.js'),
      '--capability', w.capability,
      '--ws-url', `${wsUrl}/ws`,
      '--cli', cli,
      '--cli-output-format', w.output_format || 'text',
      ...(w.model ? ['--model', w.model] : []),
    ];
  }

  const child = spawn('node', args, {
    detached: true,
    stdio: ['ignore', fs.openSync(logPath, 'w'), fs.openSync(logPath, 'a')],
    env: combinedEnv,
  });
  child.unref();
  console.log(`  [+] ${w.capability} spawned (pid ${child.pid})`);
  return child.pid || null;
}

async function main() {
  const wsUrl = process.argv[2] || 'ws://127.0.0.1:8741';
  const policyPath = path.join(ROME_ROOT, 'dictator/workers.json');
  const policy: { workers: WorkerPolicy[] } = JSON.parse(fs.readFileSync(policyPath, 'utf-8'));

  const env: Record<string, string> = {
    GEMINI_CLI: process.env.GEMINI_CLI || `${process.env.HOME}/projects/gemini-cli/bundle/gemini.js`,
    ROME_ROOT,
  };

  if (fs.existsSync(`${process.env.HOME}/.vibe/.env`)) {
    const vibeEnv = fs.readFileSync(`${process.env.HOME}/.vibe/.env`, 'utf-8');
    for (const line of vibeEnv.split('\n')) {
      const m = line.match(/^([^#][^=]*)=(.*)$/);
      if (m) env[m[1].trim()] = m[2].trim();
    }
  }

  const results: SpawnResult[] = [];
  console.log('ROME Bootstrap: probing and spawning workers...');
  for (const w of policy.workers) {
    const probeCmd = w.probe
      .replace(/\$GEMINI_CLI/g, env.GEMINI_CLI)
      .replace(/\$ROME_ROOT/g, ROME_ROOT);
    if (probe(probeCmd, env)) {
      const pid = spawnWorker(w, wsUrl, env);
      results.push({ capability: w.capability, status: 'spawned', pid });
    } else {
      console.log(`  [-] ${w.capability} skipped (probe failed)`);
      results.push({ capability: w.capability, status: 'skipped', pid: null });
    }
  }

  await new Promise<void>((resolve) => {
    const ws = new WebSocket(`${wsUrl}/ws`);
    ws.on('open', () => {
      for (const res of results) {
        ws.send(JSON.stringify({
          type: "command",
          command: "event",
          request_id: `boot-${res.capability}`,
          payload: {
            event: {
              type: "worker_spawn",
              task_id: "bootstrap",
              capability: res.capability,
              status: res.status,
              pid: res.pid
            }
          }
        }));
      }
      setTimeout(() => { ws.close(); resolve(); }, 500);
    });
    ws.on('error', (err) => {
      console.error(`  [!] WS emission failed: ${err.message}`);
      resolve();
    });
    setTimeout(() => resolve(), 3000);
  });
}

main().catch(console.error);
