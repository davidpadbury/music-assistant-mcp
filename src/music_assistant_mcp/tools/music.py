"""Music library tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from music_assistant_client import MusicAssistantClient
from pydantic import BaseModel, Field


def register_tools(
    mcp: FastMCP, get_client: Callable[[], Awaitable[MusicAssistantClient]]
):
    """Register music library tools with the MCP server."""

    class SearchInput(BaseModel):
        """Input for music search."""

        query: str = Field(
            min_length=1,
            description="Search query - artist name, album title, song name, or playlist",
        )
        media_types: list[str] | None = Field(
            default=None,
            description=(
                "Filter by media type(s): 'artist', 'album', 'track', 'playlist', 'radio'. Omit to search all types."
            ),
        )
        limit: int = Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum results per media type (1-50)",
        )

    @mcp.tool()
    async def ma_search(params: SearchInput) -> str:
        """Search for music across all configured providers.

        Returns matching artists, albums, tracks, playlists, and radio stations.
        Use the returned URIs with ma_play_media to play results.

        Examples:
        - Search for an artist: query="Beatles"
        - Search for a song: query="Yesterday", media_types=["track"]
        - Search for playlists: query="workout", media_types=["playlist"]
        """
        client = await get_client()

        # Perform search
        results = await client.music.search(
            search_query=params.query,
            media_types=params.media_types,
            limit=params.limit,
        )

        lines = [f"# Search Results for '{params.query}'\n"]

        # Helper to format items
        def format_item(item, media_type: str) -> str:
            name = getattr(item, "name", "Unknown")
            uri = getattr(item, "uri", None)

            extra = ""
            if media_type == "track":
                if hasattr(item, "artists") and item.artists:
                    artist = item.artists[0].name if item.artists else ""
                    extra = f" by {artist}"
                if hasattr(item, "album") and item.album:
                    extra += f" ({item.album.name})"
            elif media_type == "album":
                if hasattr(item, "artists") and item.artists:
                    artist = item.artists[0].name if item.artists else ""
                    extra = f" by {artist}"

            uri_str = f" `{uri}`" if uri else ""
            return f"- {name}{extra}{uri_str}"

        # Process each media type in results
        has_results = False

        if hasattr(results, "artists") and results.artists:
            has_results = True
            lines.append("## Artists")
            for item in results.artists[: params.limit]:
                lines.append(format_item(item, "artist"))
            lines.append("")

        if hasattr(results, "albums") and results.albums:
            has_results = True
            lines.append("## Albums")
            for item in results.albums[: params.limit]:
                lines.append(format_item(item, "album"))
            lines.append("")

        if hasattr(results, "tracks") and results.tracks:
            has_results = True
            lines.append("## Tracks")
            for item in results.tracks[: params.limit]:
                lines.append(format_item(item, "track"))
            lines.append("")

        if hasattr(results, "playlists") and results.playlists:
            has_results = True
            lines.append("## Playlists")
            for item in results.playlists[: params.limit]:
                lines.append(format_item(item, "playlist"))
            lines.append("")

        if hasattr(results, "radio") and results.radio:
            has_results = True
            lines.append("## Radio Stations")
            for item in results.radio[: params.limit]:
                lines.append(format_item(item, "radio"))
            lines.append("")

        if not has_results:
            lines.append("No results found.")

        lines.append("\n*Use the URI with ma_play_media to play an item.*")
        return "\n".join(lines)

    class BrowseInput(BaseModel):
        """Input for browsing music."""

        path: str | None = Field(
            default=None,
            description=(
                "Path to browse. Omit for root level (shows all providers). "
                "Use paths from previous browse results to navigate deeper."
            ),
        )

    @mcp.tool()
    async def ma_browse(params: BrowseInput) -> str:
        """Browse music provider content hierarchically.

        Start with no path to see available providers, then use returned paths
        to navigate deeper into the library structure.

        Examples:
        - See all providers: path=None
        - Browse a provider: path="spotify://library"
        - Navigate deeper: path="spotify://library/playlists"
        """
        client = await get_client()

        # Browse the path (or root if not specified)
        items = await client.music.browse(params.path)

        if params.path:
            lines = [f"# Browsing: {params.path}\n"]
        else:
            lines = ["# Music Providers\n"]

        if not items:
            lines.append("No items found at this path.")
            return "\n".join(lines)

        # Group items by type for better organization
        folders = []
        media = []

        for item in items:
            name = getattr(item, "name", "Unknown")
            uri = getattr(item, "uri", None)
            item_type = getattr(item, "media_type", None)

            # Check if this is a navigable folder/container
            is_folder = (
                hasattr(item, "is_folder") and item.is_folder
            ) or item_type in [
                "library",
                "folder",
                "provider",
            ]

            entry = {"name": name, "uri": uri, "type": item_type}

            if is_folder:
                folders.append(entry)
            else:
                media.append(entry)

        # Display folders first
        if folders:
            lines.append("## Folders")
            for item in folders:
                uri_str = f" → `{item['uri']}`" if item["uri"] else ""
                lines.append(f"- 📁 {item['name']}{uri_str}")
            lines.append("")

        # Then media items
        if media:
            lines.append("## Media")
            for item in media:
                type_icon = {
                    "artist": "👤",
                    "album": "💿",
                    "track": "🎵",
                    "playlist": "📋",
                    "radio": "📻",
                }.get(str(item["type"]), "•")
                uri_str = f" `{item['uri']}`" if item["uri"] else ""
                lines.append(f"- {type_icon} {item['name']}{uri_str}")
            lines.append("")

        lines.append(
            "\n*Use folder paths with ma_browse to navigate. Use media URIs with ma_play_media to play.*"
        )
        return "\n".join(lines)
