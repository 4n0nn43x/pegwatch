"""MCP server: the ladder as a tool for agents. Reads the public JSON of the site, so no key of any kind is needed.

    uv run --with 'mcp>=2' python -m pegwatch.mcp_server              # stdio, for Claude Desktop / Cursor / Claude Code
    PEGWATCH_URL=http://127.0.0.1:8080 python -m pegwatch.mcp_server   # against a local instance

Claude Code:  claude mcp add pegwatch -- uv run --with 'mcp>=2' --with pyyaml --with requests python -m pegwatch.mcp_server
"""

import os

import requests
from mcp.server.mcpserver import MCPServer

from .ladder import true_price as _true_price

URL = os.getenv("PEGWATCH_URL", "https://pegwatch.fyra.fun").rstrip("/")
mcp = MCPServer("pegwatch", instructions="Real price of a dollar (P2P, by payment rail) and of tokenized US stocks and gold "
                "(by wrapper, by trading regime) from any of 59 countries. Information only, never advice or execution.")


def _get(path: str) -> dict:
    r = requests.get(f"{URL}/{path}", timeout=20)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def countries() -> list[dict]:
    """Every country the ladder knows: code, name, fiat, dollar premium today, cheapest rail, wrappers open for NVDA."""
    return _get("world.json")["countries"]


@mcp.tool()
def dollar_premium(country: str) -> dict:
    """What a dollar (USDT) really costs in one country right now: official rate, premium per payment rail, buy vs sell."""
    return _get(f"ladder/{country.upper()}.json")["dollar"]


@mcp.tool()
def true_price(country: str, asset: str = "NVDA", amount: float = 1000.0) -> dict:
    """Total cost of one tokenized asset (NVDA, TSLA, GOLD...) from one country for an amount in local currency:
    dollar premium on the best rail x wrapper premium vs the real asset, per wrapper, with access status and units received."""
    return _true_price(country.upper(), asset.upper(), amount, _get(f"ladder/{country.upper()}.json"))


@mcp.tool()
def premiums() -> dict:
    """Premium of every tokenized wrapper vs its real asset (55 assets), with the trading regime and the perp oracle proxy."""
    return _get("premiums/latest.json")


if __name__ == "__main__":
    mcp.run()
