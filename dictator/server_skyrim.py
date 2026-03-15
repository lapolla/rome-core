from mcp.server.fastmcp import FastMCP
from dictator.tools_skyrim import register as register_skyrim

mcp = FastMCP("Skyrim")

register_skyrim(mcp)

if __name__ == "__main__":
    mcp.run()
