import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.cwd();
const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
const conf = fs.readFileSync(configPath, 'utf-8');
const meshPort = conf.match(/^MESH_PORT=(\d+)/m)?.[1] || '8741';
const tokenPathRel = conf.match(/^SOVEREIGN_TOKEN_PATH=(.+)/m)?.[1] || '.rome_SOVEREIGN_TOKEN';
const token = fs.readFileSync(path.join(ROME_ROOT, tokenPathRel), 'utf-8').trim();

const ws = new WebSocket(`ws://127.0.0.1:${meshPort}/ws?token=${token}`);

const [command, ...args] = process.argv.slice(2);
const payload = args.length > 0 ? JSON.parse(args[0]) : {};
const reqId = `cli-${Date.now()}`;
let myTaskId = command === 'dispatch' ? null : (payload.task_id || null);

ws.on('open', () => {
  ws.send(JSON.stringify({ type: 'command', command, request_id: reqId, payload }));
});

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === 'response' && msg.request_id === reqId) {
    if (msg.ok) {
      if (command === 'dispatch' && msg.payload && msg.payload.task_id) {
        myTaskId = msg.payload.task_id;
        process.stderr.write(`[DAEMON] Dispatched task: ${myTaskId}\n`);
      } else if (command === 'await' && msg.payload && msg.payload.tasks) {
        const task = msg.payload.tasks[0];
        if (task && task.report) {
          process.stdout.write(task.report);
        }
        ws.close();
        process.exit(0);
      } else {
        if (msg.payload && msg.payload.output !== undefined) {
          process.stdout.write(msg.payload.output);
        } else if (msg.payload) {
          process.stdout.write(JSON.stringify(msg.payload, null, 2));
        }
        ws.close();
        process.exit(0);
      }
    } else {
      process.stderr.write(msg.error || 'Unknown Error');
      ws.close();
      process.exit(1);
    }
  } else if (msg.type === 'event' && msg.event && msg.event.task_id === myTaskId && msg.event.type === 'complete') {
    if (msg.event.payload && msg.event.payload.report) {
      process.stdout.write(msg.event.payload.report);
    }
    ws.close();
    process.exit(0);
  }
});

ws.on('error', () => process.exit(1));
setTimeout(() => {
  if (!myTaskId && command === 'dispatch') process.exit(1);
}, 10000);

// Global timeout for long running tasks
setTimeout(() => process.exit(1), 600000);
