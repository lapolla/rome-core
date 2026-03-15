from mcp.server.fastmcp import FastMCP
from dictator.tools_drupal import register as register_drupal

mcp = FastMCP("Drupal")

register_drupal(mcp)

if __name__ == "__main__":
    mcp.run()
