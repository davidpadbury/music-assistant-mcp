"""Player control tools for Music Assistant MCP server."""

from collections.abc import Awaitable, Callable
from typing import Literal

from mcp.server.fastmcp import FastMCP
from music_assistant_client import MusicAssistantClient
from pydantic import BaseModel, Field


def register_tools(
    mcp: FastMCP, get_client: Callable[[], Awaitable[MusicAssistantClient]]
):
    """Register player control tools with the MCP server."""

    @mcp.tool()
    async def ma_list_players() -> str:
        """List all available players with their current state.

        Returns player IDs, names, volume levels, and group membership.
        Use this to discover available speakers before controlling them.

        Returns:
            List of players with: id, name, volume, is_group, group_members
        """
        client = await get_client()
        players = list(client.players)

        if not players:
            return "No players found. Ensure Music Assistant has player providers configured."

        lines = ["# Available Players\n"]
        for player in players:
            status_parts = []

            # Volume info
            if hasattr(player, "volume_level"):
                status_parts.append(f"Volume: {player.volume_level}%")

            # Mute status
            if hasattr(player, "volume_muted") and player.volume_muted:
                status_parts.append("(muted)")

            # Active source (e.g., "TV", "AUX", "Spotify")
            # Skip if the source is the player's own ID (means Music Assistant is the source)
            if hasattr(player, "active_source") and player.active_source:
                if player.active_source != player.player_id:
                    # Try to look up the friendly name from source_list
                    source_name = player.active_source
                    if hasattr(player, "source_list") and player.source_list:
                        for source in player.source_list:
                            if source.id == player.active_source:
                                source_name = source.name
                                break
                    status_parts.append(f"Source: {source_name}")

            # Group info
            if hasattr(player, "group_childs") and player.group_childs:
                status_parts.append(
                    f"Group leader with {len(player.group_childs)} members"
                )
            elif hasattr(player, "synced_to") and player.synced_to:
                status_parts.append(f"Synced to: {player.synced_to}")

            # State
            if hasattr(player, "state"):
                status_parts.append(f"State: {player.state}")

            status = " | ".join(status_parts) if status_parts else "No status"
            lines.append(f"- **{player.name}** (`{player.player_id}`)")
            lines.append(f"  {status}\n")

        return "\n".join(lines)

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
    async def ma_volume(params: VolumeInput) -> str:
        """Control player volume - set level, adjust up/down, or mute/unmute.

        Provide exactly one of: level, adjust, or mute.

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
