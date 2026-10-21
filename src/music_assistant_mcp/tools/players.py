"""Player control tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from music_assistant_client import MusicAssistantClient
from pydantic import BaseModel, Field

from ..client import with_reconnect
from .schemas import PlayersPayload


def _player_payload(player) -> dict[str, Any]:
    """Extract machine-readable player state (single source of truth)."""
    state = getattr(player, "playback_state", None)
    active_source = getattr(player, "active_source", None)
    source_name = None
    if active_source and active_source != player.player_id:
        for source in getattr(player, "source_list", []) or []:
            if getattr(source, "id", None) == active_source:
                source_name = getattr(source, "name", None)
                break
    return {
        "player_id": player.player_id,
        "name": player.name,
        "available": getattr(player, "available", None),
        "volume_level": getattr(player, "volume_level", None),
        "volume_muted": getattr(player, "volume_muted", None),
        "state": state.value if state is not None else None,
        "group_members": list(getattr(player, "group_members", None) or []),
        "synced_to": getattr(player, "synced_to", None),
        "active_source": active_source,
        "active_source_name": source_name,
    }


def _format_players(payload: list[dict[str, Any]]) -> str:
    """Render the players payload as human-readable text."""
    if not payload:
        return (
            "No players found. Ensure Music Assistant has player providers configured."
        )

    lines = ["# Available Players\n"]
    for p in payload:
        status_parts = []
        if p["volume_level"] is not None:
            status_parts.append(f"Volume: {p['volume_level']}%")
        if p["volume_muted"]:
            status_parts.append("(muted)")
        if p["active_source_name"]:
            status_parts.append(f"Source: {p['active_source_name']}")
        if p["group_members"]:
            status_parts.append(f"Group leader with {len(p['group_members'])} members")
        elif p["synced_to"]:
            status_parts.append(f"Synced to: {p['synced_to']}")
        if p["state"]:
            status_parts.append(f"State: {p['state']}")

        status = " | ".join(status_parts) if status_parts else "No status"
        lines.append(f"- **{p['name']}** (`{p['player_id']}`)")
        lines.append(f"  {status}\n")

    return "\n".join(lines)


def register_tools(
    mcp: MCPServer, get_client: Callable[[], Awaitable[MusicAssistantClient]]
):
    """Register player control tools with the MCP server."""

    @mcp.tool()
    @with_reconnect
    async def ma_list_players() -> Annotated[CallToolResult, PlayersPayload]:
        """List all available players with their current state.

        Returns player IDs, names, volume levels, and group membership.
        Use this to discover available speakers before controlling them.
        """
        client = await get_client()
        payload = [_player_payload(player) for player in client.players]

        return CallToolResult(
            content=[TextContent(type="text", text=_format_players(payload))],
            structured_content={"players": payload},
        )

    class VolumeInput(BaseModel):
        """Input for volume control."""

        player_id: str = Field(
            description="The player ID to control (use ma_list_players to find IDs)"
        )
        level: int | None = Field(
            default=None,
            ge=0,
            le=100,
            description="Set volume to this level (0-100). Omit to use adjust or mute instead.",
        )
        adjust: Literal["up", "down"] | None = Field(
            default=None,
            description="Adjust volume up or down by a step. Omit to use level or mute instead.",
        )
        mute: bool | None = Field(
            default=None,
            description="Set mute state. True to mute, False to unmute. Omit to use level or adjust instead.",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_volume(params: VolumeInput) -> str:
        """Control volume for a single player - set level, adjust up/down, or mute/unmute.

        Provide exactly one of: level, adjust, or mute.

        For group volume control (all players in a group), use ma_group_volume instead.

        Examples:
        - Set volume to 50%: level=50
        - Turn volume up: adjust="up"
        - Mute the player: mute=True
        """
        client = await get_client()

        # Count how many options were provided
        options_provided = sum(
            [
                params.level is not None,
                params.adjust is not None,
                params.mute is not None,
            ]
        )

        if options_provided == 0:
            return "Error: Provide one of: level (0-100), adjust ('up'/'down'), or mute (true/false)"

        if options_provided > 1:
            return "Error: Provide only one of: level, adjust, or mute"

        if params.level is not None:
            await client.players.volume_set(params.player_id, params.level)
            return f"Volume set to {params.level}% on {params.player_id}"

        if params.adjust is not None:
            if params.adjust == "up":
                await client.players.volume_up(params.player_id)
                return f"Volume increased on {params.player_id}"
            else:
                await client.players.volume_down(params.player_id)
                return f"Volume decreased on {params.player_id}"

        if params.mute is not None:
            await client.players.volume_mute(params.player_id, params.mute)
            state = "muted" if params.mute else "unmuted"
            return f"Player {params.player_id} {state}"

        return "Error: No action specified"

    class GroupVolumeInput(BaseModel):
        """Input for group volume control."""

        player_id: str = Field(
            description="Any player in the group (use ma_list_players to find group members)"
        )
        level: int | None = Field(
            default=None,
            ge=0,
            le=100,
            description="Set group volume to this level (0-100). Omit to use adjust instead.",
        )
        adjust: Literal["up", "down"] | None = Field(
            default=None,
            description="Adjust group volume up or down. Omit to use level instead.",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_group_volume(params: GroupVolumeInput) -> str:
        """Control volume for all players in a speaker group.

        Adjusts volume for all players that are grouped together. The player_id
        can be any member of the group - the volume change applies to all members.

        Provide exactly one of: level or adjust.

        Examples:
        - Set group volume to 30%: player_id="living_room", level=30
        - Turn group volume up: player_id="kitchen", adjust="up"
        - Turn group volume down: player_id="bedroom", adjust="down"
        """
        client = await get_client()

        # Validate exactly one option provided
        if params.level is None and params.adjust is None:
            return "Error: Provide either level (0-100) or adjust ('up'/'down')"

        if params.level is not None and params.adjust is not None:
            return "Error: Provide only one of: level or adjust"

        if params.level is not None:
            await client.players.group_volume(params.player_id, params.level)
            return f"Group volume set to {params.level}% on {params.player_id}"

        if params.adjust == "up":
            await client.players.group_volume_up(params.player_id)
            return f"Group volume increased on {params.player_id}"
        else:
            await client.players.group_volume_down(params.player_id)
            return f"Group volume decreased on {params.player_id}"

    class GroupInput(BaseModel):
        """Input for speaker grouping."""

        action: Literal["join", "leave"] = Field(
            description="'join' to add players to a group, 'leave' to remove from groups"
        )
        player_ids: list[str] = Field(description="List of player IDs to group/ungroup")
        target_player_id: str | None = Field(
            default=None,
            description="For 'join': the leader player to sync to. Required for join action.",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_group(params: GroupInput) -> str:
        """Manage speaker groups - join players together or remove from groups.

        For 'join': Syncs the specified players to a target player (the group leader).
        For 'leave': Removes the specified players from any sync groups.

        Examples:
        - Group kitchen speaker to living room: action="join", player_ids=["kitchen"], target_player_id="living_room"
        - Ungroup kitchen and bedroom: action="leave", player_ids=["kitchen", "bedroom"]
        """
        client = await get_client()

        if params.action == "join":
            if not params.target_player_id:
                return "Error: target_player_id is required when joining a group"

            if len(params.player_ids) == 1:
                await client.players.group(
                    params.player_ids[0], params.target_player_id
                )
            else:
                await client.players.group_many(
                    params.target_player_id, params.player_ids
                )

            player_list = ", ".join(params.player_ids)
            return f"Players [{player_list}] joined to group led by {params.target_player_id}"

        else:  # leave
            if len(params.player_ids) == 1:
                await client.players.ungroup(params.player_ids[0])
            else:
                await client.players.ungroup_many(params.player_ids)

            player_list = ", ".join(params.player_ids)
            return f"Players [{player_list}] removed from their groups"

    class AnnounceInput(BaseModel):
        """Input for announcements."""

        player_id: str = Field(
            description="The player ID to announce on (use ma_list_players to find IDs)"
        )
        message: str | None = Field(
            default=None,
            description="Text to speak on the player (TTS). Omit to use url instead.",
        )
        url: str | None = Field(
            default=None,
            description="Audio file URL to play as the announcement. Omit to use message instead.",
        )
        volume_level: int | None = Field(
            default=None,
            ge=0,
            le=100,
            description="Volume for the announcement (0-100). Defaults to current volume.",
        )
        pre_announce: bool | None = Field(
            default=None,
            description="Play a pre-announcement sound before the announcement.",
        )
        tts_engine: str | None = Field(
            default=None,
            description="TTS engine to use for the message. Defaults to the server default.",
        )

    @mcp.tool()
    @with_reconnect
    async def ma_announce(params: AnnounceInput) -> str:
        """Play an announcement (spoken message or audio file) on a player.

        Provide exactly one of: message (text to speak) or url (audio file).

        Examples:
        - Speak a message: player_id="kitchen", message="Dinner is ready"
        - Play an audio file: player_id="kitchen", url="https://example.com/alert.mp3"
        - Quiet announcement: player_id="bedroom", message="Time to wake up", volume_level=30
        """
        if (params.message is None) == (params.url is None):
            return (
                "Error: Provide exactly one of: message (TTS text) or url (audio file)"
            )

        client = await get_client()
        await client.players.play_announcement(
            player_id=params.player_id,
            url=params.url,
            message=params.message,
            volume_level=params.volume_level,
            pre_announce=params.pre_announce,
            tts_engine=params.tts_engine,
        )
        what = f"message: {params.message}" if params.message else f"url: {params.url}"
        return f"Announcement played on {params.player_id} ({what})"

    class SelectSourceInput(BaseModel):
        """Input for source selection."""

        player_id: str = Field(
            description="The player ID to switch source on (use ma_list_players to find IDs)"
        )
        source: str = Field(
            description=(
                "The source ID to activate (from the 'Source:' shown by ma_list_players "
                "or the player's source list)"
            )
        )

    @mcp.tool()
    @with_reconnect
    async def ma_select_source(params: SelectSourceInput) -> str:
        """Select an input source on a player.

        Switches the player's active input, e.g. from Music Assistant playback to
        'TV', 'AUX', 'Spotify' or a sync group. Use ma_list_players to see the
        current source; players expose their available sources.

        Examples:
        - Switch TV to its HDMI input: player_id="living_room_tv", source="HDMI 1"
        - Return a Sonos to Music Assistant playback: player_id="kitchen", source="kitchen"
        """
        client = await get_client()
        await client.players.select_source(params.player_id, params.source)
        return f"Source set to {params.source} on {params.player_id}"
