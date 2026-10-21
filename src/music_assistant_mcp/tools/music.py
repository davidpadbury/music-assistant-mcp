"""Music library tools for Music Assistant MCP server."""

import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import MediaType
from pydantic import BaseModel, Field

from ..client import tool_errors, with_reconnect
from .schemas import BrowsePayload, SearchPayload


def _media_brief(item, media_type: str) -> dict[str, Any]:
    """Extract machine-readable fields from a media item (single source of truth)."""
    brief: dict[str, Any] = {
        "name": getattr(item, "name", None),
        "uri": getattr(item, "uri", None),
        "media_type": media_type,
    }
    artists = [
        a.name for a in getattr(item, "artists", None) or [] if getattr(a, "name", None)
    ]
    if artists:
        brief["artists"] = artists
        brief["artist"] = artists[0]
    if media_type == "track":
        album = getattr(item, "album", None)
        if album is not None:
            brief["album"] = getattr(album, "name", None)
    return brief


def _search_payload(query: str, results, limit: int) -> dict[str, Any]:
    """Build the structured search payload."""
    media_types = {
        "artists": "artist",
        "albums": "album",
        "tracks": "track",
        "playlists": "playlist",
        "radio": "radio",
    }
    payload: dict[str, Any] = {"query": query}
    for key, media_type in media_types.items():
        items = getattr(results, key, None) or []
        payload[key] = [_media_brief(item, media_type) for item in items[:limit]]
    return payload


def _format_search(payload: dict[str, Any]) -> str:
    """Render the search payload as human-readable text."""
    lines = [f"# Search Results for '{payload['query']}'\n"]
    has_results = False

    for key, heading in [
        ("artists", "Artists"),
        ("albums", "Albums"),
        ("tracks", "Tracks"),
        ("playlists", "Playlists"),
        ("radio", "Radio Stations"),
    ]:
        items = payload.get(key) or []
        if not items:
            continue
        has_results = True
        lines.append(f"## {heading}")
        for item in items:
            extra = ""
            if item.get("media_type") == "track":
                if item.get("artists"):
                    extra = f" by {item['artists'][0]}"
                if item.get("album"):
                    extra += f" ({item['album']})"
            elif item.get("media_type") == "album" and item.get("artists"):
                extra = f" by {item['artists'][0]}"
            uri = item.get("uri")
            uri_str = f" `{uri}`" if uri else ""
            lines.append(f"- {item['name']}{extra}{uri_str}")
        lines.append("")

    if not has_results:
        lines.append("No results found.")

    lines.append("\n*Use the URI with ma_play_media to play an item.*")
    return "\n".join(lines)


def _get_browse_path(uri: str | None) -> str | None:
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


def _browse_payload(
    path: str | None, all_items, offset: int, limit: int
) -> dict[str, Any]:
    """Build the structured browse payload from raw browse items."""
    items = all_items[offset : offset + limit]
    folders = []
    media = []
    for item in items:
        name = getattr(item, "name", "Unknown")
        uri = getattr(item, "uri", None)
        item_type = getattr(item, "media_type", None)

        is_folder = (hasattr(item, "is_folder") and item.is_folder) or item_type in [
            "library",
            "folder",
            "provider",
        ]

        if is_folder:
            browse_path = _get_browse_path(uri)
            folders.append({"name": name, "path": browse_path, "type": item_type})
        else:
            media.append({"name": name, "uri": uri, "type": item_type})

    return {
        "path": path,
        "total": len(all_items),
        "offset": offset,
        "limit": limit,
        "folders": folders,
        "media": media,
    }


# Matches media URIs from ma_search that resolve to a playable tracklist:
# e.g. library://album/766, apple_music://album/12345
_ALBUM_URI = re.compile(r"^(?P<provider>[\w-]+)://album/(?P<item_id>[^/]+)$")


def _album_tracklist_payload(
    uri: str | None, tracks, offset: int, limit: int
) -> dict[str, Any]:
    """Build a browse-shaped payload listing an album's tracks."""
    media = [
        {
            "name": getattr(track, "name", None),
            "uri": getattr(track, "uri", None),
            "type": "track",
        }
        for track in tracks
    ]
    return {
        "path": uri,
        "total": len(media),
        "offset": offset,
        "limit": limit,
        "folders": [],
        "media": media[offset : offset + limit],
        "kind": "album_tracks",
    }


def _format_browse(payload: dict[str, Any]) -> str:
    """Render the browse payload as human-readable text."""
    path = payload["path"]
    total = payload["total"]
    offset = payload["offset"]
    folders = payload["folders"]
    media = payload["media"]

    if path:
        lines = [f"# Browsing: {path}\n"]
    else:
        lines = ["# Music Providers\n"]

    if total == 0:
        lines.append("No items found at this path.")
        return "\n".join(lines)

    if offset >= total:
        lines.append(f"Offset {offset} exceeds total items ({total}).")
        return "\n".join(lines)

    if folders:
        lines.append("## Folders")
        for item in folders:
            path_str = f" → `{item['path']}`" if item["path"] else ""
            lines.append(f"- 📁 {item['name']}{path_str}")
        lines.append("")

    if media:
        heading = "Tracks" if payload.get("kind") == "album_tracks" else "Media"
        lines.append(f"## {heading}")
        type_icon = {
            "artist": "👤",
            "album": "💿",
            "track": "🎵",
            "playlist": "📋",
            "radio": "📻",
        }
        for item in media:
            uri_str = f" `{item['uri']}`" if item["uri"] else ""
            lines.append(
                f"- {type_icon.get(str(item['type']), '•')} {item['name']}{uri_str}"
            )
        lines.append("")

    showing_end = offset + len(folders) + len(media)
    has_more = showing_end < total

    if has_more:
        lines.append(
            f"\n**Showing {offset + 1}-{showing_end} of {total} items.** "
            f"Use `offset={showing_end}` to see more, or use `ma_search` to find specific items."
        )
    else:
        lines.append(f"\n*Showing {offset + 1}-{showing_end} of {total} items.*")

    lines.append(
        "\n*Use folder paths with ma_browse to navigate. Use media URIs with ma_play_media to play.*"
    )
    return "\n".join(lines)


def register_tools(
    mcp: MCPServer, get_client: Callable[[], Awaitable[MusicAssistantClient]]
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
    @tool_errors
    async def ma_search(
        params: SearchInput,
    ) -> Annotated[CallToolResult, SearchPayload]:
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

        payload = _search_payload(params.query, results, params.limit)
        return CallToolResult(
            content=[TextContent(type="text", text=_format_search(payload))],
            structured_content=payload,
        )

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
    @tool_errors
    async def ma_browse(
        params: BrowseInput,
    ) -> Annotated[CallToolResult, BrowsePayload]:
        """Browse music provider content hierarchically.

        Start with no path to see available providers, then use returned paths
        to navigate deeper into the library structure.

        Examples:
        - See all providers: path=None
        - Browse a provider: path="spotify://library"
        - Navigate deeper: path="spotify://library/playlists"
        """
        client = await get_client()

        # An album URI from ma_search resolves to its tracklist
        album_match = _ALBUM_URI.match(params.path or "")
        if album_match:
            tracks = await client.music.get_album_tracks(
                album_match["item_id"], album_match["provider"]
            )
            payload = _album_tracklist_payload(
                params.path, tracks, params.offset, params.limit
            )
        else:
            # Browse the path (or root if not specified)
            all_items = await client.music.browse(params.path)
            payload = _browse_payload(
                params.path, all_items, params.offset, params.limit
            )

        return CallToolResult(
            content=[TextContent(type="text", text=_format_browse(payload))],
            structured_content=payload,
        )
