# =============================================================================
# StockAgent MCP server
# Exposes stock/finance tools (backed by Alpha Vantage) to Claude Desktop via MCP.
# Requirements:
#   - python -m pip install fastmcp python-dotenv requests
#   - .env must contain ALPHA_VANTAGE_API_KEY (and optional ALPHA_VANTAGE_BASE_URL)
#   - Tools are implemented in src/langgraph_agent/tools.py
# Launch (Claude Desktop uses this internally via uv/mcp CLI):
#   uv run --with mcp[cli] mcp run server.py
# =============================================================================

from dotenv import load_dotenv          # loads .env -> os.environ
load_dotenv()

from mcp.server.fastmcp import FastMCP

# Import tool implementations
from src.langgraph_agent.tools import (
    get_realtime_stock,
    search_ticker,
    get_company_overview,
    get_earnings_data,
    get_historical_stock_data,
)

# Create the MCP app
mcp = FastMCP("StockAgent")

# Register each function as an MCP tool.
# NOTE: We rebind names so the MCP-decorated versions are exported.
get_realtime_stock         = mcp.tool()(get_realtime_stock)
search_ticker              = mcp.tool()(search_ticker)
get_company_overview       = mcp.tool()(get_company_overview)
get_earnings_data          = mcp.tool()(get_earnings_data)
get_historical_stock_data  = mcp.tool()(get_historical_stock_data)