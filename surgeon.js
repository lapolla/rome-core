import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.cwd();
const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
const conf = fs.readFileSync(configPath, 'utf-8');
const meshPort = conf.match(/^MESH_PORT=(\\d+)/m)?.[1] || '8741';
const tokenPathRel = conf.match(/^SOVEREIGN_TOKEN_PATH=(.+)/m)?.[1] || '.rome_SOVEREIGN_TOKEN';
const token = fs.readFileSync(path.join(ROME_ROOT, tokenPathRel), 'utf-8').trim();

const [capability, prompt] = process.argv.slice(2);
if (!capability || !prompt) {
    console.error('Usage: node surgeon.js <CAPABILITY> "<PROMPT>"');
    process.exit(1);
}

const ws = new WebSocket(`ws://127.0.0.1:${meshPort}/ws?token=${token}`);
const reqId = `surgeon-${Date.now()}`;
let myTaskId = null;

ws.on('open', () => {
    ws.send(JSON.stringify({ 
        type: 'command', 
        command: 'dispatch', 
        request_id: reqId, 
        payload: { capability, prompt } 
    }));
});

ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    
    // 1. Capture Task ID
    if (msg.type === 'response' && msg.request_id === reqId && msg.ok) {
        myTaskId = msg.payload.task_id;
    } 
    
    // 2. Wait for Completion Event
    if (msg.type === 'event' && msg.event && msg.event.task_id === myTaskId && msg.event.type === 'complete') {
        if (msg.event.payload && msg.event.payload.report) {
            process.stdout.write(msg.event.payload.report);
        } else {
            process.stdout.write(JSON.stringify(msg.event.payload, null, 2));
        }
        ws.close();
        process.exit(0);
    }
    
    // 3. Handle Errors
    if (msg.type === 'response' && msg.request_id === reqId && !msg.ok) {
        console.error(msg.error);
        ws.close();
        process.exit(1);
    }
});

ws.on('error', (err) => {
    console.error('WS Error:', err);
    process.exit(1);
});

// Timeout
setTimeout(() => {
    console.error('Surgeon timeout');
    process.exit(1);
}, 30000);
