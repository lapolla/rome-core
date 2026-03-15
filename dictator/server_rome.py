from mcp.server.fastmcp import FastMCP
from dictator.tools_legion import register as register_legion
from dictator.tools_docs import register as register_docs
from dictator.tools_gc import register as register_gc
from dictator.tools_stats import register as register_stats
from dictator.tools_prefect import register as register_prefect

mcp = FastMCP("ROME")

register_legion(mcp)
register_docs(mcp)
register_gc(mcp)
register_stats(mcp)
register_prefect(mcp)

if __name__ == "__main__":
    mcp.run()
