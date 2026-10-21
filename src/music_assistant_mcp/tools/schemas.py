"""Typed output schemas for structured tool results.

Return annotations on the read tools reference these models, so the schema
is advertised in `tools/list` outputSchema and every structured_content
payload is validated against them before going on the wire.
"""

from pydantic import BaseModel, Field


class PlayerBrief(BaseModel):
    """Machine-readable player state."""

    player_id: str
    name: str | None = None
    available: bool | None = None
    volume_level: int | None = None
    volume_muted: bool | None = None
    state: str | None = None
    group_members: list[str] = []
    synced_to: str | None = None
    active_source: str | None = None
    active_source_name: str | None = None


class PlayersPayload(BaseModel):
    """Result of ma_list_players."""

    players: list[PlayerBrief]


class MediaBrief(BaseModel):
    """Machine-readable media item (search result)."""

    name: str | None = None
    uri: str | None = None
    media_type: str
    artist: str | None = Field(
        default=None,
        description="Primary artist name (first of `artists`). Prefer this scalar over the list.",
    )
    artists: list[str] = Field(
        default=[],
        description="All artist names, in order. This is a LIST, not a scalar.",
    )
    album: str | None = None


class SearchPayload(BaseModel):
    """Result of ma_search."""

    query: str
    artists: list[MediaBrief] = []
    albums: list[MediaBrief] = []
    tracks: list[MediaBrief] = []
    playlists: list[MediaBrief] = []
    radio: list[MediaBrief] = []


class QueueSettings(BaseModel):
    """Machine-readable queue settings."""

    shuffle: bool | None = None
    repeat: str | None = None
    autoplay: bool | None = None
    smart_shuffle: bool | None = None
    smart_fades: bool | None = None
    crossfade: bool | None = None


class QueueItemBrief(BaseModel):
    """Machine-readable queue item."""

    index: int
    queue_item_id: str | None = None
    name: str | None = None
    uri: str | None = None
    duration: int | None = None


class NowPlaying(BaseModel):
    """Machine-readable currently-playing item."""

    queue_item_id: str | None = None
    name: str | None = None
    artist: str | None = Field(
        default=None,
        description="Primary artist name (first of `artists`). Prefer this scalar over the list.",
    )
    artists: list[str] = Field(
        default=[],
        description="All artist names, in order. This is a LIST, not a scalar.",
    )
    index: int | None = None


class QueuePayload(BaseModel):
    """Machine-readable queue state."""

    queue_id: str
    total_items: int
    offset: int
    limit: int
    has_more: bool
    state: str | None = None
    is_playing: bool = False
    settings: QueueSettings
    now_playing: NowPlaying | None = None
    items: list[QueueItemBrief] = []


class QueueResult(BaseModel):
    """Result of ma_queue."""

    queue: QueuePayload | None = None


class BrowseItem(BaseModel):
    """Machine-readable browse entry (folder or media item)."""

    name: str
    path: str | None = None
    uri: str | None = None
    type: str | None = None


class BrowsePayload(BaseModel):
    """Result of ma_browse."""

    path: str | None = None
    total: int
    offset: int
    limit: int
    kind: str = "browse"
    folders: list[BrowseItem] = []
    media: list[BrowseItem] = []
