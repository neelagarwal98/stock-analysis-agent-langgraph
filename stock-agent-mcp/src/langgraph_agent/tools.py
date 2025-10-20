# =============================================================================
# Alpha Vantage–backed tools used by the MCP server.
# Provides real-time price, ticker search, overview, earnings, and historical summaries.
# =============================================================================

import os
import requests
from typing import Dict


# ── HTTP helper ──────────────────────────────────────────────────────────────
def alpha_vantage_call(params: Dict[str, str]) -> dict:
    """
    Make a request to the Alpha Vantage API with the given parameters.

    Automatically:
      - Reads base URL and API key from environment variables.
      - Adds the API key to params.
      - Performs a GET and returns parsed JSON.
      - Raises for non-2xx HTTP responses.

    Env vars:
      - ALPHA_VANTAGE_API_KEY        (required)
      - ALPHA_VANTAGE_BASE_URL       (optional, defaults to official endpoint)

    Args:
        params: Querystring params for Alpha Vantage.

    Returns:
        JSON-decoded response as a dict.
    """
    base_url = os.getenv("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")
    api_key  = os.getenv("ALPHA_VANTAGE_API_KEY")
    params   = dict(params)  # avoid mutating caller

    if not api_key:
        return {"error": "Missing ALPHA_VANTAGE_API_KEY in environment"}

    params["apikey"] = api_key
    resp = requests.get(base_url, params=params)
    resp.raise_for_status()
    data = resp.json()

    # Common API “rate limit / error” shapes
    if isinstance(data, dict) and ("Note" in data or "Error Message" in data):
        return {"error": data.get("Note") or data.get("Error Message")}

    return data


# ── Tools ────────────────────────────────────────────────────────────────────
def get_realtime_stock(symbol: str) -> str:
    """
    Fetches the latest available intraday stock price for the given symbol.

    API Reference:
        https://www.alphavantage.co/documentation/#intraday

    Args:
        symbol (str): Stock ticker symbol (e.g., "AAPL", "MSFT").

    Returns:
        str: Latest stock price in USD, formatted to 2 decimal places.
             Returns an error message if no data is available.
    """
    data = alpha_vantage_call({
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol.upper(),
        "interval": "5min",
    })
    if "error" in data:
        return f"Error fetching real-time data for {symbol}: {data['error']}"

    ts = data.get("Time Series (5min)")
    if not ts:
        return f"Error: Could not fetch real-time data for {symbol}."

    latest_ts = max(ts.keys())
    price = float(ts[latest_ts]["1. open"])
    return f"The latest price for {symbol.upper()} is ${price:.2f}."


def search_ticker(company_name: str) -> str:
    """
    Searches for ticker symbols that match the given company name.

    API Reference:
        https://www.alphavantage.co/documentation/#symbolsearch

    Args:
        company_name (str): Partial or full name of the company.

    Returns:
        str: List of matching ticker symbols with company name and region.
             Returns a message if no results are found.
    """
    data = alpha_vantage_call({
        "function": "SYMBOL_SEARCH",
        "keywords": company_name,
    })
    if "error" in data:
        return f"Error searching '{company_name}': {data['error']}"

    matches = data.get("bestMatches", [])
    if not matches:
        return f"No ticker symbols found for {company_name}."

    lines = [f"{m['1. symbol']} – {m['2. name']} ({m['4. region']})" for m in matches]
    return f"Search results for '{company_name}':\n" + "\n".join(lines)


def get_company_overview(symbol: str) -> str:
    """
    Retrieves a company's overview and key financial metrics.

    API Reference:
        https://www.alphavantage.co/documentation/#company-overview

    Args:
        symbol (str): Stock ticker symbol.

    Returns:
        str: Overview including sector, industry, market cap, revenue, EPS, and P/E ratio.
             Returns a message if no data is found.
    """
    data = alpha_vantage_call({
        "function": "OVERVIEW",
        "symbol": symbol.upper(),
    })
    if "error" in data:
        return f"Error fetching overview for {symbol}: {data['error']}"

    if not data or "Name" not in data:
        return f"No company overview found for {symbol}."

    return (
        f"Company Overview for {symbol.upper()}:\n"
        f"Name: {data['Name']}\n"
        f"Sector: {data.get('Sector')}\n"
        f"Industry: {data.get('Industry')}\n"
        f"Market Cap: {data.get('MarketCapitalization')}\n"
        f"Revenue (TTM): {data.get('RevenueTTM')}\n"
        f"EPS: {data.get('EPS')}\n"
        f"P/E Ratio: {data.get('PERatio')}"
    )


def get_earnings_data(symbol: str) -> str:
    """
    Fetches the most recent quarterly earnings report for the given symbol.

    API Reference:
        https://www.alphavantage.co/documentation/#earnings

    Args:
        symbol (str): Stock ticker symbol.

    Returns:
        str: Latest quarterly earnings data (fiscal date, reported EPS, estimated EPS).
             Returns a message if no earnings data is found.
    """
    data = alpha_vantage_call({
        "function": "EARNINGS",
        "symbol": symbol.upper(),
    })
    if "error" in data:
        return f"Error fetching earnings for {symbol}: {data['error']}"

    q = data.get("quarterlyEarnings", [])
    if not q:
        return f"No recent earnings data available for {symbol}."

    latest = q[0]
    return (
        f"Earnings Data for {symbol.upper()}:\n"
        f"- Fiscal Date Ending: {latest.get('fiscalDateEnding')}\n"
        f"- Reported EPS: {latest.get('reportedEPS')}\n"
        f"- Estimated EPS: {latest.get('estimatedEPS', 'N/A')}"
    )


def get_historical_stock_data(symbol: str, interval: str = "daily") -> str:
    """
    Fetches and summarizes historical stock price data for the given symbol and interval.

    Only summary metrics are returned (latest date, open/close price, highest/lowest price,
    total trading volume).

    API Reference:
        https://www.alphavantage.co/documentation/

    Args:
        symbol (str): Stock ticker symbol.
        interval (str): Time interval for historical data. Options:
                        "daily" (default), "weekly", "monthly".

    Returns:
        str: Summary of historical stock performance.
             Returns an error message if data is unavailable.
    """
    function = {
        "daily": "TIME_SERIES_DAILY",
        "weekly": "TIME_SERIES_WEEKLY",
        "monthly": "TIME_SERIES_MONTHLY",
    }.get(interval.lower(), "TIME_SERIES_DAILY")

    data = alpha_vantage_call({"function": function, "symbol": symbol.upper()})
    if "error" in data:
        return f"Error fetching {interval} data for {symbol}: {data['error']}"

    # Find the time series key robustly
    ts_key = next((k for k in data.keys() if "Time Series" in k), None)
    if not ts_key:
        return f"Failed to fetch {interval.title()} data for {symbol.upper()}."
    ts = data.get(ts_key, {})
    if not ts:
        return f"Failed to fetch {interval.title()} data for {symbol.upper()}."

    latest_date = max(ts.keys())
    latest = ts[latest_date]
    highest = max(float(v["2. high"]) for v in ts.values())
    lowest  = min(float(v["3. low"])  for v in ts.values())
    volume  = sum(int(v.get("5. volume", 0)) for v in ts.values())

    return (
        f"Summary of {symbol.upper()} ({interval.title()}):\n"
        f"- Latest Date: {latest_date}\n"
        f"- Open Price: ${float(latest['1. open']):.2f}\n"
        f"- Close Price: ${float(latest['4. close']):.2f}\n"
        f"- Highest Price: ${highest:.2f}\n"
        f"- Lowest Price: ${lowest:.2f}\n"
        f"- Total Volume: {volume:,} shares"
    )
