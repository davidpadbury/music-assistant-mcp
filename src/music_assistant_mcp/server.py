"""Music Assistant MCP Server.

Provides tools for controlling Music Assistant through the Model Context Protocol.
"""

from mcp.server.fastmcp import FastMCP

from .client import get_client
from .tools import music, playback, players, queue

# Create the MCP server
mcp = FastMCP("music-assistant")

# Register tools from each module
players.register_tools(mcp, get_client)
playback.register_tools(mcp, get_client)
queue.register_tools(mcp, get_client)
music.register_tools(mcp, get_client)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
