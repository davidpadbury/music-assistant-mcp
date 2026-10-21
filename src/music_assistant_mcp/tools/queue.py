"""Queue management tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, Protocol

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from music_assistant_models.enums import RepeatMode
from pydantic import BaseModel, Field

from ..client import with_reconnect

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient


class PlayerQueuesProtocol(Protocol):
    """Protocol for player_queues interface used by queue formatting."""

    def __iter__(self): ...
    async def get_queue_items(
        self, queue_id: str, limit: int = 500, offset: int = 0
    ): ...


def _queue_settings(queue) -> dict[str, Any]:
    """Machine-readable queue settings."""
    return {
        "shuffle": getattr(queue, "shuffle_enabled", None),
        "repeat": getattr(queue, "repeat_mode", None),
        "autoplay": getattr(queue, "autoplay_enabled", None),
        "smart_shuffle": getattr(queue, "smart_shuffle_active", None),
        "smart_fades": getattr(queue, "smart_fades_active", None),
        "crossfade": getattr(queue, "crossfade_enabled", None),
    }


def _queue_item_brief(item, index: int) -> dict[str, Any]:
    """Extract machine-readable fields from a queue item."""
    return {
        "index": index,
        "queue_item_id": getattr(item, "queue_item_id", None),
        "name": getattr(item, "name", None),
        "uri": getattr(item, "uri", None),
        "duration": getattr(item, "duration", None),
    }


async def build_queue_payload(
    player_queues: PlayerQueuesProtocol,
    queue_id: str,
    offset: int = 0,
    limit: int = 20,
    player_state: str | None = None,
) -> dict[str, Any] | None:
    """Build the machine-readable queue payload. None when the queue is unknown."""
    queue = next((q for q in player_queues if q.queue_id == queue_id), None)
    if queue is None:
        return None

    items = []
    if queue.items > 0:
        items = list(
            await player_queues.get_queue_items(queue_id, limit=limit, offset=offset)
        )

    item_briefs = [
        _queue_item_brief(item, offset + idx) for idx, item in enumerate(items)
    ]

    now_playing = None
    current = getattr(queue, "current_item", None)
    if current is not None:
        current_id = getattr(current, "queue_item_id", None)
        now_index = next(
            (b["index"] for b in item_briefs if b["queue_item_id"] == current_id),
            None,
        )
        media_item = getattr(current, "media_item", None)
        artists = (
            [
                a.name
                for a in (getattr(media_item, "artists", None) or [])
                if getattr(a, "name", None)
            ]
            if media_item is not None
            else []
        )
        now_playing = {
            "queue_item_id": current_id,
            "name": getattr(current, "name", None),
            "artists": artists,
        }
        if now_index is not None:
            now_playing["index"] = now_index

    return {
        "queue_id": queue_id,
        "total_items": queue.items,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(item_briefs) < queue.items,
        "state": player_state,
        "is_playing": player_state == "playing",
        "settings": _queue_settings(queue),
        "now_playing": now_playing,
        "items": item_briefs,
    }


def format_queue_state(payload: dict[str, Any] | None) -> str:
    """Render the queue payload as human-readable text."""
    if payload is None:
        return "Queue not found. Use ma_list_players to find valid IDs."

    queue_id = payload["queue_id"]
    lines = [f"# Queue: {queue_id}\n"]

    state = payload.get("state")
    if state:
        lines.append(f"**State:** {state}\n")

    settings = []
    s = payload["settings"]
    if s.get("shuffle") is not None:
        settings.append(f"Shuffle: {'on' if s['shuffle'] else 'off'}")
    if s.get("repeat") is not None:
        settings.append(f"Repeat: {s['repeat']}")
    if settings:
        lines.append(f"**Settings:** {' | '.join(settings)}\n")

    now_playing = payload.get("now_playing")
    if now_playing:
        name = now_playing.get("name")
        artists = now_playing.get("artists") or []
        artist = f" by {artists[0]}" if artists else ""
        idx = now_playing.get("index")
        idx_str = f" (queue index {idx})" if idx is not None else ""
        lines.append(f"**Now Playing:** {name}{artist}{idx_str}\n")

    items = payload["items"]
    total = payload["total_items"]
    if items:
        lines.append("**Queue:**")
        for item in items:
            lines.append(
                f"{item['index'] + 1}. {item['name']} (`{item['queue_item_id']}`)"
            )
        if payload["has_more"]:
            remaining = total - payload["offset"] - len(items)
            lines.append(f"... and {remaining} more items")
    elif total > 0:
        lines.append(
            f"No items in this range (offset {payload['offset']}, limit {payload['limit']})."
        )
    else:
        lines.append("Queue is empty")

    return "\n".join(lines)


def register_tools(
    mcp: MCPServer, get_client: Callable[[], Awaitable["MusicAssistantClient"]]
):
    """Register queue management tools with the MCP server."""

    class QueueInput(BaseModel):
        """Input for queue state and settings."""

        queue_id: str = Field(description="The queue/player ID to get or modify")
        get_items: bool = Field(
            default=True,
            description="Include queue items in the response",
        )
        shuffle: bool | None = Field(
            default=None,
            description="Set shuffle mode: True to enable, False to disable",
        )
        repeat: Literal["off", "one", "all"] | None = Field(
            default=None,
            description="Set repeat mode: 'off', 'one' (repeat current track), or 'all' (repeat queue)",
        )
        clear: bool = Field(
            default=False,
            description="Clear all items from the queue",
        )
        offset: int = Field(
            default=0,
            ge=0,
            description="Number of queue items to skip (for pagination)",
        )
        limit: int = Field(
            default=20,
            ge=1,
            le=100,
            description="Maximum queue items to return (1-100)",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_queue(params: QueueInput) -> CallToolResult:
        """Get queue state and items, or modify queue settings.

        Use this to:
        - See what's currently playing and queued
        - Enable/disable shuffle
        - Set repeat mode (off, one, all)
        - Clear the queue

        Multiple settings can be changed in one call.
        """
        client = await get_client()
        queues = client.player_queues
        results = []

        # Apply settings changes first
        if params.shuffle is not None:
            await queues.shuffle(params.queue_id, params.shuffle)
            state = "enabled" if params.shuffle else "disabled"
            results.append(f"Shuffle {state}")

        if params.repeat is not None:
            repeat_mode = RepeatMode(params.repeat)
            await queues.repeat(params.queue_id, repeat_mode)
            results.append(f"Repeat set to '{params.repeat}'")

        if params.clear:
            await queues.clear(params.queue_id)
            results.append("Queue cleared")

        # Get queue state
        if params.get_items and not params.clear:
            player_state = None
            for player in client.players:
                if player.player_id == params.queue_id:
                    ps = getattr(player, "playback_state", None)
                    player_state = ps.value if ps is not None else None
                    break

            payload = await build_queue_payload(
                queues, params.queue_id, params.offset, params.limit, player_state
            )
            output = format_queue_state(payload)
            if results:
                output = "**Changes applied:** " + ", ".join(results) + "\n\n" + output
            return CallToolResult(
                content=[TextContent(type="text", text=output)],
                structured_content={"queue": payload},
            )

        if results:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text", text="Changes applied: " + ", ".join(results)
                    )
                ]
            )

        return CallToolResult(
            content=[
                TextContent(type="text", text="No changes made and get_items=False")
            ]
        )

    class QueueItemInput(BaseModel):
        """Input for managing individual queue items."""

        queue_id: str = Field(description="The queue/player ID")
        item_id: str = Field(
            description="The queue item ID to manage (from ma_queue output)"
        )
        action: Literal["move_up", "move_down", "move_next", "remove"] = Field(
            description=(
                "Action to perform: "
                "'move_up' = move one position earlier, "
                "'move_down' = move one position later, "
                "'move_next' = move to play next, "
                "'remove' = remove from queue"
            )
        )

    @mcp.tool()
    @with_reconnect
    async def ma_queue_item(params: QueueItemInput) -> str:
        """Manage individual items in the queue.

        Use ma_queue first to see queue items and their IDs, then use this
        tool to reorder or remove specific items.

        Actions:
        - move_up: Move the item one position earlier in the queue
        - move_down: Move the item one position later in the queue
        - move_next: Move the item to play immediately after the current track
        - remove: Remove the item from the queue
        """
        client = await get_client()
        queues = client.player_queues

        if params.action == "move_up":
            await queues.move_up(params.queue_id, params.item_id)
            return f"Moved item {params.item_id} up in queue"

        elif params.action == "move_down":
            await queues.move_down(params.queue_id, params.item_id)
            return f"Moved item {params.item_id} down in queue"

        elif params.action == "move_next":
            await queues.move_next(params.queue_id, params.item_id)
            return f"Moved item {params.item_id} to play next"

        elif params.action == "remove":
            await queues.delete_item(params.queue_id, params.item_id)
            return f"Removed item {params.item_id} from queue"

        return f"Unknown action: {params.action}"

    class TransferQueueInput(BaseModel):
        """Input for transferring a queue between players."""

        source_queue_id: str = Field(description="The queue/player to transfer from")
        target_queue_id: str = Field(description="The queue/player to transfer to")

    @mcp.tool()
    @with_reconnect
    async def ma_transfer_queue(params: TransferQueueInput) -> str:
        """Transfer playback from one player to another.

        Moves the entire playback state (queue, position, settings) from the
        source player to the target player.

        Example: Transfer what's playing on the kitchen speaker to the living room.
        """
        client = await get_client()
        await client.player_queues.transfer_queue(
            params.source_queue_id, params.target_queue_id
        )
        return f"Transferred queue from {params.source_queue_id} to {params.target_queue_id}"
