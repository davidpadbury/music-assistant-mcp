"""Playback control tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable
from typing import Literal

from mcp.server.fastmcp import FastMCP
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import QueueOption
from pydantic import BaseModel, Field

from ..client import with_reconnect


def register_tools(
    mcp: FastMCP, get_client: Callable[[], Awaitable[MusicAssistantClient]]
):
    """Register playback control tools with the MCP server."""

    class PlaybackInput(BaseModel):
        """Input for playback control."""

        queue_id: str = Field(
            description="The queue/player ID to control (typically same as player_id)"
        )
        command: Literal["play", "pause", "stop", "toggle", "next", "previous"] = Field(
            description="Playback command: play, pause, stop, toggle (play/pause), next, previous"
        )
        seek_seconds: int | None = Field(
            default=None,
            description="Optional: seek to this position in seconds (only with 'play' command)",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_playback(params: PlaybackInput) -> str:
        """Control playback state - play, pause, stop, skip tracks, or seek.

        Commands:
        - play: Start or resume playback
        - pause: Pause playback
        - stop: Stop playback completely
        - toggle: Toggle between play and pause
        - next: Skip to next track
        - previous: Go to previous track

        Use seek_seconds with 'play' to jump to a specific position.
        """
        client = await get_client()
        queues = client.player_queues

        if params.command == "play":
            if params.seek_seconds is not None:
                await queues.seek(params.queue_id, params.seek_seconds)
                return (
                    f"Seeked to {params.seek_seconds}s and playing on {params.queue_id}"
                )
            await queues.play(params.queue_id)
            return f"Playing on {params.queue_id}"

        elif params.command == "pause":
            await queues.pause(params.queue_id)
            return f"Paused {params.queue_id}"

        elif params.command == "stop":
            await queues.stop(params.queue_id)
            return f"Stopped {params.queue_id}"

        elif params.command == "toggle":
            await queues.play_pause(params.queue_id)
            return f"Toggled play/pause on {params.queue_id}"

        elif params.command == "next":
            await queues.next(params.queue_id)
            return f"Skipped to next track on {params.queue_id}"

        elif params.command == "previous":
            await queues.previous(params.queue_id)
            return f"Went to previous track on {params.queue_id}"

        return f"Unknown command: {params.command}"

    class PlayMediaInput(BaseModel):
        """Input for playing media."""

        queue_id: str = Field(description="The queue/player ID to play on")
        media: str | list[str] = Field(
            description="Media URI(s) to play. Get URIs from ma_search or ma_browse."
        )
        option: Literal["play", "replace", "next", "add"] = Field(
            default="play",
            description=(
                "How to handle the queue: "
                "'play' = clear queue and play immediately, "
                "'replace' = replace queue but keep settings, "
                "'next' = insert as next track, "
                "'add' = add to end of queue"
            ),
        )
        radio_mode: bool = Field(
            default=False,
            description="Enable radio mode to auto-play similar tracks when queue ends",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_play_media(params: PlayMediaInput) -> str:
        """Play media on a player/queue.

        First use ma_search to find media and get URIs, then use this tool to play them.

        Options:
        - play: Clears the queue and starts playing immediately
        - replace: Replaces queue contents but respects current settings
        - next: Adds the media as the next track(s) to play
        - add: Adds to the end of the current queue

        Radio mode will continue playing similar music after the queue ends.
        """
        client = await get_client()

        # Normalize media to list
        media_list = params.media if isinstance(params.media, list) else [params.media]

        # Map option string to QueueOption enum
        option_map = {
            "play": QueueOption.PLAY,
            "replace": QueueOption.REPLACE,
            "next": QueueOption.NEXT,
            "add": QueueOption.ADD,
        }

        await client.player_queues.play_media(
            queue_id=params.queue_id,
            media=media_list,
            option=option_map[params.option],
            radio_mode=params.radio_mode,
        )

        media_count = len(media_list)
        action = {
            "play": "Playing",
            "replace": "Replaced queue with",
            "next": "Added as next",
            "add": "Added to queue",
        }[params.option]

        radio_note = " (radio mode enabled)" if params.radio_mode else ""
        return f"{action} {media_count} item(s) on {params.queue_id}{radio_note}"
