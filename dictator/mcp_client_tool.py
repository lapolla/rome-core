#!/usr/bin/env python3
import sys
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    if len(sys.argv) < 3:
        print("Usage: mcp_client_tool.py <tool_name> [tool_args_json]")
        sys.exit(1)

    tool_name = sys.argv[1]
    tool_args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    # This client is designed to be called BY a worker (legion) 
    # to talk to the Dictator (MCP Server) via stdio.
    # However, in ROME, the Dictator is the one calling the worker.
    # This tool is for cross-tool communication if needed.
    
    server_params = StdioServerParameters(
        command="python3",
        args=["/home/paul-kane/projects/rome-core/dictator/dictator.py"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=tool_args)
            
            for item in result.content:
                if item.type == "text":
                    print(item.text)

if __name__ == "__main__":
    asyncio.run(main())
