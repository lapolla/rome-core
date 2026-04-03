from mcp.server.fastmcp import FastMCP
from dictator.tools_desktop import register as register_desktop

mcp = FastMCP("Desktop")

register_desktop(mcp)

if __name__ == "__main__":
    mcp.run()
