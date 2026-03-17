import asyncio
import json
import yaml
import websockets
import os
import sys
from typing import Any, Dict, Set


ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
CONFIG_PATH = os.path.join(ROME_ROOT, "dictator", "config.json")
_WS_URL = os.environ.get("ROME_WS_URL", "ws://127.0.0.1:8741/ws")


def _ws_headers() -> Dict[str, str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        token = str(cfg.get("ws_token") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    except Exception:
        return {}


class WsMultiplexer:
    """Single recv loop that routes responses and events."""

    def __init__(self, ws):
        self.ws = ws
        self.events: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._pending: Dict[str, asyncio.Future] = {}
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._recv_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _recv_loop(self):
        try:
            while True:
                raw = await self.ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == "response":
                    req_id = msg.get("request_id")
                    fut = self._pending.pop(req_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg.get("payload", {}))
                elif msg.get("type") == "event":
                    await self.events.put(msg.get("event", {}))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    async def send_command(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        req_id = os.urandom(4).hex()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        await self.ws.send(json.dumps({
            "type": "command",
            "command": command,
            "request_id": req_id,
            "payload": payload,
        }))
        return await fut


async def run_campaign(campaign_file: str) -> None:
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign_data = yaml.safe_load(f)

    name = campaign_data.get("name", "Unnamed")
    task_defs = {t["id"]: t for t in campaign_data.get("tasks", [])}
    if not task_defs:
        print("No tasks.", file=sys.stderr)
        return

    statuses: Dict[str, str] = {tid: "pending" for tid in task_defs}
    results: Dict[str, Dict[str, Any]] = {}
    total = len(task_defs)

    print(f"Campaign: {name} ({total} tasks)")

    async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
        mux = WsMultiplexer(ws)
        mux.start()

        # Skip agent_hello
        await mux.events.get()

        dispatched: Set[str] = set()

        try:
            while True:
                done = sum(1 for s in statuses.values() if s in ("completed", "failed", "cancelled", "SUCCESS"))
                if done == total:
                    break

                # Dispatch ready tasks
                for tid, tdef in task_defs.items():
                    if statuses[tid] != "pending" or tid in dispatched:
                        continue
                    deps = tdef.get("depends_on", [])
                    if all(statuses.get(d) in ("completed", "SUCCESS") for d in deps):
                        print(f"-> {tid}")
                        dispatched.add(tid)
                        try:
                            resp = await mux.send_command("dispatch", {
                                "task_id": tid,
                                "capability": tdef["capability"],
                                "prompt": tdef["prompt"],
                                "input_files": tdef.get("input_files"),
                                "fire_and_forget": True,
                            })
                            if resp.get("accepted"):
                                statuses[tid] = "running"
                            else:
                                statuses[tid] = "failed"
                                results[tid] = {"status": "failed", "error": resp.get("error")}
                                print(f"   REJECTED: {resp.get('error')}", file=sys.stderr)
                        except Exception as e:
                            statuses[tid] = "failed"
                            results[tid] = {"status": "failed", "error": str(e)}
                            print(f"   ERROR: {e}", file=sys.stderr)

                # Drain events
                try:
                    event = await asyncio.wait_for(mux.events.get(), timeout=1.0)
                    if event.get("type") == "complete" and event.get("task_id") in task_defs:
                        tid = event["task_id"]
                        p = event.get("payload", {})
                        status = p.get("status", "unknown")
                        statuses[tid] = status
                        results[tid] = {"status": status, "report_path": p.get("report_path"), "usage": p.get("usage", {})}
                        cost = p.get("usage", {}).get("cost_usd", 0)
                        print(f"   {tid} -> {status} (${cost:.3f})")

                        if status not in ("completed", "SUCCESS"):
                            for dep_tid, dep_def in task_defs.items():
                                if tid in dep_def.get("depends_on", []):
                                    statuses[dep_tid] = "failed"
                                    results[dep_tid] = {"status": "failed", "error": f"dep {tid} failed"}
                                    print(f"   {dep_tid} -> SKIPPED (dep failed)")
                except asyncio.TimeoutError:
                    pass

        finally:
            await mux.stop()

        print(f"\n--- {name} ---")
        for tid in task_defs:
            r = results.get(tid, {"status": statuses[tid]})
            print(f"  {tid}: {r['status']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python loader.py <campaign.yaml>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run_campaign(sys.argv[1]))


if __name__ == "__main__":
    main()
