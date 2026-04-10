import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const ROME_ROOT = process.env.ROME_ROOT || process.cwd();

export async function executeShell(
  taskId: string,
  command: string,
  wsSender?: (ev: any) => Promise<void>
): Promise<{ status: 'SUCCESS' | 'FAILED'; report: string; exit_code: number; elapsed_s: number }> {
  const taskDir = path.join(ROME_ROOT, 'legions', taskId);
  if (!fs.existsSync(taskDir)) {
    fs.mkdirSync(taskDir, { recursive: true });
  }

  const startTs = Date.now();
  const shellTimeout = parseInt(process.env.SHELL_TIMEOUT || '600', 10);
  const chunks: Buffer[] = [];
  let timedOut = false;
  let lineCount = 0;
  let totalLineCount = 0;
  let lastProgressTs = Date.now();

  return new Promise((resolve) => {
    const proc = spawn('bash', ['-c', command], {
      detached: true,
      cwd: taskDir,
      env: {
        ...process.env,
        ROME_TASK_ID: taskId,
        ROME_TASK_DIR: taskDir
      }
    });

    const timeout = setTimeout(() => {
      timedOut = true;
      try {
        // Kill process group
        process.kill(-proc.pid!, 'SIGKILL');
      } catch (e) {}
    }, shellTimeout * 1000);

    const onData = (data: Buffer) => {
      chunks.push(data);
      const output = data.toString('utf-8');
      const lines = output.split('\n');
      lineCount += lines.length - 1;
      totalLineCount += lines.length - 1;
      const now = Date.now();
      const elapsed = (now - startTs) / 1000;
      
      if (wsSender && (lineCount >= 5 || elapsed < 2 || now - lastProgressTs >= 2000)) {
        const lastLine = lines[lines.length - 1] || lines[lines.length - 2] || '';
        const message = lastLine.trim().slice(0, 80);
        const percent = Math.min(1 + Math.floor(totalLineCount / 5), 99);
        
        wsSender({
          type: 'progress',
          task_id: taskId,
          payload: {
            percent,
            message
          }
        }).catch(() => {});
        lineCount = 0;
        lastProgressTs = now;
      }
    };

    proc.stdout.on('data', onData);
    proc.stderr.on('data', onData);

    proc.on('close', (code) => {
      clearTimeout(timeout);
      if (timedOut) {
          chunks.push(Buffer.from(`\n[TIMEOUT] Process killed after ${shellTimeout}s\n`));
      }
      const elapsed_s = (Date.now() - startTs) / 1000;
      const status = (code === 0 && !timedOut) ? 'SUCCESS' : 'FAILED';
      const report = Buffer.concat(chunks).toString('utf-8').slice(0, 4000);
      
      resolve({
        status,
        report,
        exit_code: code ?? -1,
        elapsed_s: Math.round(elapsed_s * 1000) / 1000
      });
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      const elapsed_s = (Date.now() - startTs) / 1000;
      chunks.push(Buffer.from(`\n[ERROR] ${err.message}\n`));
      resolve({
        status: 'FAILED',
        report: Buffer.concat(chunks).toString('utf-8').slice(0, 4000),
        exit_code: -1,
        elapsed_s: Math.round(elapsed_s * 1000) / 1000
      });
    });
  });
}
