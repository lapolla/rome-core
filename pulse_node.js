import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.cwd();
const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
const conf = fs.readFileSync(configPath, 'utf-8');
const meshPort = conf.match(/^MESH_PORT=(\\d+)/m)?.[1] || '8741';
const tokenPathRel = conf.match(/^SOVEREIGN_TOKEN_PATH=(.+)/m)?.[1] || '.rome_SOVEREIGN_TOKEN';
const token = fs.readFileSync(path.join(ROME_ROOT, tokenPathRel), 'utf-8').trim();

console.log(`\x1b[35m[PULSE] Initiating Full-Duplex Mesh Node on port ${meshPort}...\x1b[0m`);
const ws = new WebSocket(`ws://127.0.0.1:${meshPort}/ws?token=${token}`);

const activeTasks = new Map();

ws.on('open', () => {
    console.log('\x1b[35m[PULSE] Node Online. Emitting Signals...\x1b[0m');
    
    // Dispatching multiple tasks into the duplex stream concurrently
    dispatch('NATIVE_SHELL', 'pwd', 'Get Root');
    dispatch('SAFE_SHELL', 'sleep 2 && echo "Task 1 Done"', 'Slow Task');
    dispatch('SAFE_SHELL', 'echo "Task 2 Done"', 'Fast Task');
});

function dispatch(capability, prompt, intent) {
    const reqId = `pulse-${Math.random().toString(36).substring(7)}`;
    ws.send(JSON.stringify({
        type: 'command',
        command: 'dispatch',
        request_id: reqId,
        payload: { capability, prompt, intent }
    }));
}

ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    
    // 1. Handle command acknowledgments
    if (msg.type === 'response' && msg.ok && msg.payload?.task_id) {
        activeTasks.set(msg.payload.task_id, { status: 'dispatched' });
        console.log(`\x1b[32m[SIGNAL_ACK] Task ${msg.payload.task_id} accepted by Mesh.\x1b[0m`);
    }

    // 2. Handle ASYNCHRONOUS events (The actual Full Duplex stream)
    if (msg.type === 'event' && msg.event) {
        const ev = msg.event;
        const tid = ev.task_id;

        if (ev.type === 'progress') {
            console.log(`\x1b[36m[PULSE_EVENT] Task ${tid} Progress: ${ev.payload.percent}% - ${ev.payload.message}\x1b[0m`);
        }

        if (ev.type === 'complete') {
            console.log(`\x1b[35m[PULSE_COMPLETE] Task ${tid} Resolved: ${ev.payload.status}\x1b[0m`);
            console.log(`\x1b[37m${ev.payload.report}\x1b[0m`);
            activeTasks.delete(tid);
            
            // If all tasks are done, we exit - but we stayed alive for the stream
            if (activeTasks.size === 0) {
                console.log('\x1b[35m[PULSE] All signals resolved. Node Offline.\x1b[0m');
                ws.close();
                process.exit(0);
            }
        }
    }
});

ws.on('error', (err) => console.error('\x1b[31m[PULSE_ERROR]\x1b[0m', err));
