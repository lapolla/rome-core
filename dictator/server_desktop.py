from mcp.server.fastmcp import FastMCP
from dictator.tools_desktop import register as register_desktop
from dictator.tools_media import register as register_media

mcp = FastMCP("Desktop")

register_desktop(mcp)
register_media(mcp)

if __name__ == "__main__":
    mcp.run()
