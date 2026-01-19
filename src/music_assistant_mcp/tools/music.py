"""Music library tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import MediaType
from pydantic import BaseModel, Field

from ..client import with_reconnect


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
    @with_reconnect
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

        # Convert string media types to enum, default to all types
        if params.media_types:
            media_types = [MediaType(mt) for mt in params.media_types]
        else:
            media_types = MediaType.ALL

        # Perform search
        results = await client.music.search(
            search_query=params.query,
            media_types=media_types,
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
        limit: int = Field(
            default=20,
            ge=1,
            le=100,
            description="Maximum items to return (1-100)",
        )
        offset: int = Field(
            default=0,
            ge=0,
            description="Number of items to skip for pagination",
        )

    @mcp.tool()
    @with_reconnect
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
        all_items = await client.music.browse(params.path)
        total_count = len(all_items)

        # Apply pagination
        items = all_items[params.offset : params.offset + params.limit]

        if params.path:
            lines = [f"# Browsing: {params.path}\n"]
        else:
            lines = ["# Music Providers\n"]

        if not all_items:
            lines.append("No items found at this path.")
            return "\n".join(lines)

        if params.offset >= total_count:
            lines.append(f"Offset {params.offset} exceeds total items ({total_count}).")
            return "\n".join(lines)

        # Group items by type for better organization
        folders = []
        media = []

        def get_browse_path(uri: str | None) -> str | None:
            """Convert URI to browse path by removing 'folder/' segment.

            The Music Assistant API returns URIs like 'provider://folder/albums'
            but browse() expects paths like 'provider://albums'.
            """
            if not uri:
                return None
            # Transform: provider://folder/subpath -> provider://subpath
            if "://folder/" in uri:
                return uri.replace("://folder/", "://")
            return uri

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

            if is_folder:
                # Folders need path transformed for browse navigation
                browse_path = get_browse_path(uri)
                folders.append({"name": name, "path": browse_path, "type": item_type})
            else:
                # Media items use 'uri' for playback
                media.append({"name": name, "uri": uri, "type": item_type})

        # Display folders first
        if folders:
            lines.append("## Folders")
            for item in folders:
                path_str = f" → `{item['path']}`" if item["path"] else ""
                lines.append(f"- 📁 {item['name']}{path_str}")
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

        # Pagination info and guidance
        showing_end = params.offset + len(items)
        has_more = showing_end < total_count

        if has_more:
            lines.append(
                f"\n**Showing {params.offset + 1}-{showing_end} of {total_count} items.** "
                f"Use `offset={showing_end}` to see more, or use `ma_search` to find specific items."
            )
        else:
            lines.append(
                f"\n*Showing {params.offset + 1}-{showing_end} of {total_count} items.*"
            )

        lines.append(
            "\n*Use folder paths with ma_browse to navigate. Use media URIs with ma_play_media to play.*"
        )
        return "\n".join(lines)
