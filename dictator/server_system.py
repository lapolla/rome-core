from mcp.server.fastmcp import FastMCP
from dictator.tools_fs import register as register_fs
from dictator.tools_git import register as register_git
from dictator.tools_ws import register as register_ws

mcp = FastMCP("System")

register_fs(mcp)
register_git(mcp)
register_ws(mcp)

if __name__ == "__main__":
    mcp.run()
