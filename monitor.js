import { WebSocket } from 'ws';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.cwd();
const configPath = path.join(ROME_ROOT, 'dictator', 'rome.conf');
const conf = fs.readFileSync(configPath, 'utf-8');
const meshPort = conf.match(/^MESH_PORT=(\\d+)/m)?.[1] || '8741';
const tokenPathRel = conf.match(/^SOVEREIGN_TOKEN_PATH=(.+)/m)?.[1] || '.rome_SOVEREIGN_TOKEN';
const token = fs.readFileSync(path.join(ROME_ROOT, tokenPathRel), 'utf-8').trim();

console.log(`\x1b[32m[MONITOR] Connecting to Mesh on port ${meshPort}...\x1b[0m`);
const ws = new WebSocket(`ws://127.0.0.1:${meshPort}/ws?token=${token}`);

ws.on('open', () => {
    console.log('\x1b[32m[MONITOR] Connection established. Streaming Mesh Traffic...\x1b[0m\n');
});

ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    const timestamp = new Date().toISOString().split('T')[1].split('Z')[0];
    
    let color = '\x1b[37m'; // White
    if (msg.type === 'event') color = '\x1b[36m'; // Cyan
    if (msg.type === 'response') color = '\x1b[32m'; // Green
    if (msg.type === 'daemon_hello') color = '\x1b[35m'; // Magenta

    console.log(`${color}[${timestamp}] ${JSON.stringify(msg, null, 2)}\x1b[0m`);
});

ws.on('error', (err) => console.error('\x1b[31m[MONITOR] WS Error:\x1b[0m', err));
ws.on('close', () => console.log('\x1b[31m[MONITOR] Connection Closed.\x1b[0m'));
