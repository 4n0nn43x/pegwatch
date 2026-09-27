"""Record a real MCP session against the public server with the official Python client, as Markdown.

    python docs/proof/record_mcp_session.py                        # https://pegwatch.fyra.fun/mcp -> docs/proof/mcp_session.md
    python docs/proof/record_mcp_session.py http://127.0.0.1:8081/mcp

Each call is printed with its arguments, latency, the sha256 of the raw text the server returned, and the result
(long lists cut). Rerun it to check the server answers the same way.
"""

import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from mcp import Client

URL = sys.argv[1] if len(sys.argv) > 1 else "https://pegwatch.fyra.fun/mcp"
OUT = Path(__file__).with_name("mcp_session.md")
CALLS = [("true_price", {"country": "BJ", "asset": "NVDA", "amount": 300000}),
         ("dollar_premium", {"country": "NG"}),
         ("monday_scoreboard", {}),
         ("countries", {})]


def cut(x, n=4):
    """Keep the shape, drop the bulk: lists beyond n items are replaced by a count."""
    if isinstance(x, list):
        return [cut(v, n) for v in x[:n]] + ([f"... {len(x) - n} more"] if len(x) > n else [])
    if isinstance(x, dict):
        return {k: cut(v, n) for k, v in x.items()}
    return x


async def main() -> None:
    lines = [f"# MCP session, {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC", "",
             f"Recorded by `docs/proof/record_mcp_session.py` with the official `mcp` Python client {version('mcp')}, "
             f"Streamable HTTP, against `{URL}`. No key, no auth.", ""]
    async with Client(URL) as client:
        t = time.monotonic()
        tools = (await client.list_tools()).tools
        lines += [f"## tools/list ({(time.monotonic() - t) * 1000:.0f} ms)", "",
                  "| Tool | Arguments | Description |", "|---|---|---|"]
        lines += [f"| `{x.name}` | {', '.join(x.input_schema.get('properties', {})) or 'none'} | {' '.join(x.description.split())} |" for x in tools]
        for name, args in CALLS:
            t = time.monotonic()
            res = await client.call_tool(name, args)
            ms = (time.monotonic() - t) * 1000
            texts = [c.text for c in res.content if getattr(c, "type", "") == "text"]   # a list result comes one item per block
            text = "\n".join(texts)
            body = res.structured_content or (json.loads(texts[0]) if len(texts) == 1 else [json.loads(x) for x in texts])
            lines += ["", f"## tools/call `{name}`", "",
                      f"Arguments `{json.dumps(args)}`, {ms:.0f} ms, is_error={res.is_error}, "
                      f"{len(text):,} bytes, sha256 `{hashlib.sha256(text.encode()).hexdigest()}`", "",
                      "```json", json.dumps(cut(body), indent=1, ensure_ascii=False), "```"]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{len(CALLS)} calls -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
