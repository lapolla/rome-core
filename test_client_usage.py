import asyncio
import sys
import os

# Ensure the project root is in sys.path
sys.path.insert(0, os.getcwd())

from dictator.ws_client import send_command_async

async def test():
    try:
        print("Dispatching task...")
        # send_command_async takes (command, payload, timeout)
        res = await send_command_async(
            command="dispatch",
            payload={
                "task_id": "test-client-1",
                "capability": "NATIVE_SHELL",
                "prompt": "echo Hello from Gemini CLI"
            },
            timeout=10.0
        )
        print(f"Dispatch result: {res}")
        
        print("Awaiting completion...")
        # await command payload needs task_ids
        status = await send_command_async(
            command="await",
            payload={"task_ids": ["test-client-1"]},
            timeout=15.0
        )
        print(f"Completion status: {status}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
