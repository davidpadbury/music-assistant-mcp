"""Queue management tools for Music Assistant MCP server."""

from typing import Awaitable, Callable, Literal, Optional

from mcp.server.fastmcp import FastMCP
from music_assistant_client import MusicAssistantClient
from pydantic import BaseModel, Field


def register_tools(
    mcp: FastMCP, get_client: Callable[[], Awaitable[MusicAssistantClient]]
):
    """Register queue management tools with the MCP server."""

    class QueueInput(BaseModel):
        """Input for queue state and settings."""

        queue_id: str = Field(
            description="The queue/player ID to get or modify"
        )
        get_items: bool = Field(
            default=True,
            description="Include queue items in the response",
        )
        shuffle: Optional[bool] = Field(
            default=None,
            description="Set shuffle mode: True to enable, False to disable",
        )
        repeat: Optional[Literal["off", "one", "all"]] = Field(
            default=None,
            description="Set repeat mode: 'off', 'one' (repeat current track), or 'all' (repeat queue)",
        )
        clear: bool = Field(
            default=False,
            description="Clear all items from the queue",
        )

    @mcp.tool()
    async def ma_queue(params: QueueInput) -> str:
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
            await queues.repeat(params.queue_id, params.repeat)
            results.append(f"Repeat set to '{params.repeat}'")

        if params.clear:
            await queues.clear(params.queue_id)
            results.append("Queue cleared")

        # Get queue state
        if params.get_items and not params.clear:
            # Find the queue in the client's queue list
            queue = None
            for q in client.player_queues:
                if q.queue_id == params.queue_id:
                    queue = q
                    break

            if queue is None:
                return f"Queue not found: {params.queue_id}. Use ma_list_players to find valid IDs."

            lines = [f"# Queue: {params.queue_id}\n"]

            # Queue settings
            settings = []
            if hasattr(queue, "shuffle_enabled"):
                settings.append(f"Shuffle: {'on' if queue.shuffle_enabled else 'off'}")
            if hasattr(queue, "repeat_mode"):
                settings.append(f"Repeat: {queue.repeat_mode}")
            if settings:
                lines.append(f"**Settings:** {' | '.join(settings)}\n")

            # Current track
            if hasattr(queue, "current_item") and queue.current_item:
                item = queue.current_item
                name = getattr(item, "name", "Unknown")
                artist = ""
                if hasattr(item, "media_item") and item.media_item:
                    if hasattr(item.media_item, "artists") and item.media_item.artists:
                        artist = f" by {item.media_item.artists[0].name}"
                lines.append(f"**Now Playing:** {name}{artist}\n")

            # Queue items
            if hasattr(queue, "items") and queue.items:
                lines.append("**Queue:**")
                for i, item in enumerate(queue.items[:20], 1):  # Limit to 20 items
                    name = getattr(item, "name", "Unknown")
                    lines.append(f"{i}. {name} (`{item.queue_item_id}`)")
                if len(queue.items) > 20:
                    lines.append(f"... and {len(queue.items) - 20} more items")
            else:
                lines.append("Queue is empty")

            if results:
                lines.insert(0, "**Changes applied:** " + ", ".join(results) + "\n")

            return "\n".join(lines)

        if results:
            return "Changes applied: " + ", ".join(results)

        return "No changes made and get_items=False"

    class QueueItemInput(BaseModel):
        """Input for managing individual queue items."""

        queue_id: str = Field(
            description="The queue/player ID"
        )
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
