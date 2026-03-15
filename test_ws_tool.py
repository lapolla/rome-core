import asyncio
import json
from dictator.tools_ws import register
from mcp.server.fastmcp import FastMCP

async def test():
    mcp = FastMCP("test")
    register(mcp)
    
    # We need to find the registered tool
    ws_send = None
    for tool in mcp._tools.values():
        if tool.name == "ws_send":
            ws_send = tool.fn
            break
            
    if not ws_send:
        print("ws_send tool not found")
        return

    print("Calling ws_send('ping')...")
    try:
        result = await ws_send(command="ping")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    import os
    # Add project root to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    asyncio.run(test())
