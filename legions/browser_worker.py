#!/usr/bin/env python3
"""
ROME BROWSER LEGIONARY
Captures screenshots and audits web surfaces natively.
Output: [ROME_STATUS: SUCCESS] + path to screenshot.png
"""
import sys
import os
import asyncio
import json
import time
from pathlib import Path

# Mock or real puppeteer call via subprocess or library
# For this environment, we'll use a python wrapper or direct cli if available.
# Since we need a reliable result, we will use a small node script dispatched via this python wrapper.

NODE_SCRIPT = """
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({width: 1920, height: 1080});
  await page.goto(process.argv[2], {waitUntil: 'networkidle0'});
  await page.screenshot({path: process.argv[3], fullPage: true});
  await browser.close();
  console.log('SCREENSHOT_DONE');
})();
"""

async def run_browser(task_id, url):
    # ROME_TASK_DIR is usually the absolute path to the task dir
    task_dir_raw = os.environ.get("ROME_TASK_DIR")
    if task_dir_raw:
        task_dir = Path(task_dir_raw).absolute()
    else:
        # Fallback for local testing
        task_dir = Path(f"./legions/{task_id}").absolute()
    
    task_dir.mkdir(parents=True, exist_ok=True)
    
    script_path = task_dir / "capture.js"
    output_path = task_dir / "screenshot.png"
    
    script_path.write_text(NODE_SCRIPT)
    
    print(f"0% + [0.0s] Launching Native Browser for {url}")
    
    cmd = ["node", str(script_path), url, str(output_path)]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode == 0 and output_path.exists():
        import base64
        with open(output_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            data_uri = f"data:image/png;base64,{encoded_string}"
        
        print(f"100% o [{time.time()}] Capture complete. Streaming to mesh...")
        
        # Submit via WS (Sovereign)
        try:
            from dictator.ws_client import send_command_async
            async def _submit():
                await send_command_async("submit_result", {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "content": f"SCREENSHOT_ATTACHED\n{data_uri}"
                })
            await _submit()
        except Exception as e:
            print(f"WS Submit Failed: {e}")

        print("[ROME_STATUS: SUCCESS]")
    else:
        print(f"FAILED: {stderr.decode()}")
        print("[ROME_STATUS: FAILED]")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Expected: browser_worker.py <task_id> <timestamp> <url>
        print("Usage: browser_worker.py <task_id> <url>")
        sys.exit(1)
    
    tid = sys.argv[1]
    url = sys.argv[-1] # Centurion passes prompt as last arg
    asyncio.run(run_browser(tid, url))
