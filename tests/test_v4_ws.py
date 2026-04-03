import asyncio
import json
import time
import unittest
from dictator.ws_client import send_command_async

class TestRomeV4Smoke(unittest.IsolatedAsyncioTestCase):
    async def test_native_shell_latency(self):
        """Smoke test for sub-millisecond native DSA latency."""
        t0 = time.monotonic()
        resp = await send_command_async("native_shell", {"command": "echo 'V4_DSA_SMOKE_TEST'"})
        elapsed = time.monotonic() - t0
        
        self.assertTrue(resp["ok"], f"NATIVE_SHELL failed: {resp.get('error')}")
        self.assertEqual(resp["stdout"].strip(), "V4_DSA_SMOKE_TEST")
        # Ensure latency is within acceptable 'native' bounds (< 100ms for control roundtrip)
        self.assertLess(elapsed, 0.1, f"NATIVE_SHELL too slow: {elapsed:.3f}s")
        print(f"V4 Native Shell Latency: {elapsed*1000:.2f}ms")

    async def test_worker_registration(self):
        """Verify at least one persistent worker is registered (e.g., GEMINI)."""
        resp = await send_command_async("workers", {})
        self.assertTrue(resp["ok"])
        workers = resp.get("workers", [])
        self.assertGreater(len(workers), 0, "No persistent workers registered!")
        
        caps = [c for w in workers for c in w["capabilities"]]
        self.assertIn("GEMINI", caps, "GEMINI worker not found in registry")
        print(f"V4 Workers Registered: {len(workers)} ({', '.join(caps)})")

    async def test_persistent_worker_dispatch(self):
        """Dispatch a dummy task to the persistent SAFE_SHELL worker."""
        # We use SAFE_SHELL for the smoke test as it is fast and deterministic.
        task_id = f"SMOKE_DISPATCH_{int(time.time())}"
        resp = await send_command_async("dispatch", {
            "task_id": task_id,
            "capability": "SAFE_SHELL",
            "prompt": "echo 'V4_WORKER_SMOKE_SUCCESS'"
        })

        self.assertTrue(resp.get("accepted"), f"Dispatch rejected: {resp}")
        # The daemon returns 'routed_to' in its response.
        self.assertEqual(resp.get("routed_to"), "persistent_worker", f"Task NOT routed to persistent worker! Response: {resp}")

        # Await completion
        max_retries = 15
        status = "unknown"
        for _ in range(max_retries):
            status_resp = await send_command_async("status", {"task_id": task_id})
            status = status_resp["task"].get("status")
            if status == "completed":
                break
            await asyncio.sleep(1)

        self.assertEqual(status, "completed")

        print(f"V4 Persistent Dispatch: SUCCESS (routed to {resp.get('routed_to')})")

if __name__ == "__main__":
    unittest.main()
