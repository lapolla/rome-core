import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { EventEmitter } from 'events';

const ROME_ROOT = process.env.ROME_ROOT || process.cwd();

export function executeShell(
  taskId: string,
  command: string,
  wsSender?: (ev: any) => Promise<void>,
  cancelEmitter?: EventEmitter
): Promise<{ status: 'SUCCESS' | 'FAILED'; report: string; exit_code: number; elapsed_s: number }> & { kill?: () => void } {
  const taskDir = path.join(ROME_ROOT, 'legions', taskId);
  if (!fs.existsSync(taskDir)) {
    fs.mkdirSync(taskDir, { recursive: true });
  }

  const startTs = Date.now();
  const chunks: Buffer[] = [];
  let interrupted = false;
  let interruptReason = '';
  let lineCount = 0;
  let totalLineCount = 0;
  let lastProgressTs = Date.now();
  let proc!: ReturnType<typeof spawn>;

  const promise = new Promise<{ status: 'SUCCESS' | 'FAILED'; report: string; exit_code: number; elapsed_s: number }>((resolve) => {
    proc = spawn('bash', ['-c', command], {
      detached: true,
      cwd: taskDir,
      env: {
        ...process.env,
        ROME_TASK_ID: taskId,
        ROME_TASK_DIR: taskDir
      }
    });

    const handleCancel = (id: string) => {
      if (id === taskId) {
        interrupted = true;
        interruptReason = 'CANCEL';
        try { process.kill(-proc.pid!, 'SIGKILL'); } catch (e) {}
      }
    };

    const handleTimeout = (id: string) => {
      if (id === taskId) {
        interrupted = true;
        interruptReason = 'TIMEOUT';
        try { process.kill(-proc.pid!, 'SIGKILL'); } catch (e) {}
      }
    };

    if (cancelEmitter) {
      cancelEmitter.on('cancel', handleCancel);
      cancelEmitter.on('timeout', handleTimeout);
    }

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

    proc.stdout?.on('data', onData);
    proc.stderr?.on('data', onData);

    const cleanup = () => {
      if (cancelEmitter) {
        cancelEmitter.removeListener('cancel', handleCancel);
        cancelEmitter.removeListener('timeout', handleTimeout);
      }
    };

    proc.on('close', (code: number) => {
      cleanup();
      if (interrupted) {
          chunks.push(Buffer.from(`\n[${interruptReason}] Process killed\n`));
      }
      const elapsed_s = (Date.now() - startTs) / 1000;
      const status = (code === 0 && !interrupted) ? 'SUCCESS' : 'FAILED';
      const report = Buffer.concat(chunks).toString('utf-8').slice(0, 4000);

      resolve({
        status,
        report,
        exit_code: code ?? -1,
        elapsed_s: Math.round(elapsed_s * 1000) / 1000
      });
    });

    proc.on('error', (err: Error) => {
      cleanup();
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

  (promise as any).kill = () => {
    if (proc && proc.pid) {
      try { process.kill(-proc.pid, 'SIGTERM'); } catch (e) {}
    }
  };

  return promise;
}
