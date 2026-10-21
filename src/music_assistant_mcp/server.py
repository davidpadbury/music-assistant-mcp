"""Music Assistant MCP Server.

Provides tools for controlling Music Assistant through the Model Context Protocol.
"""

import os
from collections.abc import Mapping

from mcp.server.mcpserver import MCPServer

from .client import get_client
from .tools import music, playback, players, queue

# Create the MCP server
mcp = MCPServer("music-assistant")

# Register tools from each module
players.register_tools(mcp, get_client)
playback.register_tools(mcp, get_client)
queue.register_tools(mcp, get_client)
music.register_tools(mcp, get_client)


def http_bind_settings(env: Mapping[str, str] | None = None) -> tuple[str, int]:
    """Resolve streamable-http bind settings from the environment."""
    if env is None:
        env = os.environ
    port_raw = env.get("MCP_PORT", "8844")
    try:
        port = int(port_raw)
    except ValueError:
        raise ValueError(
            f"Invalid MCP_PORT: {port_raw!r}; expected an integer"
        ) from None
    if not 0 <= port <= 65535:
        raise ValueError(f"Invalid MCP_PORT: {port}; must be between 0 and 65535")
    return env.get("MCP_HOST", "127.0.0.1"), port


def main():
    """Run the MCP server.

    Transport is selected by the MCP_TRANSPORT environment variable:
    - "stdio" (default): spawned by MCP clients over standard input/output.
      Limited to protocol version 2025-11-25 (the latest handshake version).
    - "streamable-http": serves on MCP_HOST/MCP_PORT and speaks the modern
      2026-07-28 protocol, required by proxies that only support it.
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "streamable-http":
        host, port = http_bind_settings()
        mcp.run(transport="streamable-http", host=host, port=port)
    elif transport == "stdio":
        mcp.run()
    else:
        raise ValueError(
            f"Unknown MCP_TRANSPORT: {transport!r}. Use 'stdio' or 'streamable-http'."
        )


if __name__ == "__main__":
    main()
