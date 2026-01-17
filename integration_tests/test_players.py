"""Integration tests for player tools."""

import pytest
from music_assistant_client import MusicAssistantClient

from .conftest import poll_until


class TestListPlayers:
    """Tests for ma_list_players functionality."""

    async def test_list_players_returns_players(self, client: MusicAssistantClient):
        """List players returns at least one player."""
        players = list(client.players)
        assert len(players) > 0, "Expected at least one player"

    async def test_players_have_required_attributes(self, client: MusicAssistantClient):
        """Each player has name, player_id, and volume_level."""
        players = list(client.players)
        for player in players:
            assert hasattr(player, "name"), "Player missing name"
            assert hasattr(player, "player_id"), "Player missing player_id"
            assert hasattr(player, "volume_level"), "Player missing volume_level"


class TestVolumeControl:
    """Tests for ma_volume functionality."""

    async def test_set_volume(
        self, client: MusicAssistantClient, player_id: str, player_volume: int
    ):
        """Setting volume changes the player volume."""
        # Choose a distinctly different target volume
        target = 50 if player_volume < 40 else 20

        await client.players.volume_set(player_id, target)

        async def volume_is_target():
            await client.players.fetch_state()
            player = next(p for p in client.players if p.player_id == player_id)
            return player.volume_level == target

        assert await poll_until(volume_is_target), (
            f"Volume should have changed to {target}"
        )

        # Restore original volume
        await client.players.volume_set(player_id, player_volume)

    async def test_volume_up(
        self, client: MusicAssistantClient, player_id: str, player_volume: int
    ):
        """Volume up increases volume."""
        # Get current volume
        await client.players.fetch_state()
        player = next(p for p in client.players if p.player_id == player_id)
        initial = player.volume_level

        # Ensure we're not at max
        if initial >= 95:
            await client.players.volume_set(player_id, 50)
            await poll_until(
                lambda: self._get_volume(client, player_id, 50),
            )
            initial = 50

        await client.players.volume_up(player_id)

        async def volume_increased():
            await client.players.fetch_state()
            player = next(p for p in client.players if p.player_id == player_id)
            return player.volume_level > initial

        assert await poll_until(volume_increased), "Volume should have increased"

        # Restore original volume
        await client.players.volume_set(player_id, player_volume)

    async def test_volume_down(
        self, client: MusicAssistantClient, player_id: str, player_volume: int
    ):
        """Volume down decreases volume."""
        # Get current volume
        await client.players.fetch_state()
        player = next(p for p in client.players if p.player_id == player_id)
        initial = player.volume_level

        # Ensure we're not at min
        if initial <= 5:
            await client.players.volume_set(player_id, 50)
            await poll_until(
                lambda: self._get_volume(client, player_id, 50),
            )
            initial = 50

        await client.players.volume_down(player_id)

        async def volume_decreased():
            await client.players.fetch_state()
            player = next(p for p in client.players if p.player_id == player_id)
            return player.volume_level < initial

        assert await poll_until(volume_decreased), "Volume should have decreased"

        # Restore original volume
        await client.players.volume_set(player_id, player_volume)

    async def _get_volume(
        self, client: MusicAssistantClient, player_id: str, expected: int
    ) -> bool:
        """Helper to check if volume matches expected."""
        await client.players.fetch_state()
        player = next(p for p in client.players if p.player_id == player_id)
        return player.volume_level == expected

    async def test_mute_unmute(self, client: MusicAssistantClient, player_id: str):
        """Mute and unmute work correctly."""
        # Mute
        await client.players.volume_mute(player_id, True)

        async def is_muted():
            await client.players.fetch_state()
            player = next(p for p in client.players if p.player_id == player_id)
            return player.volume_muted is True

        assert await poll_until(is_muted), "Player should be muted"

        # Unmute
        await client.players.volume_mute(player_id, False)

        async def is_unmuted():
            await client.players.fetch_state()
            player = next(p for p in client.players if p.player_id == player_id)
            return player.volume_muted is False

        assert await poll_until(is_unmuted), "Player should be unmuted"


class TestPlayerGrouping:
    """Tests for ma_group functionality."""

    @pytest.mark.xfail(
        reason="Ungroup state doesn't propagate reliably through Music Assistant"
    )
    async def test_group_and_ungroup(
        self, client: MusicAssistantClient, two_player_ids: tuple[str, str]
    ):
        """Grouping and ungrouping players works."""
        leader_id, follower_id = two_player_ids

        # Ensure both start ungrouped
        await client.players.ungroup(follower_id)

        async def is_ungrouped():
            await client.players.fetch_state()
            follower = next(p for p in client.players if p.player_id == follower_id)
            leader = next(p for p in client.players if p.player_id == leader_id)
            return not follower.synced_to and follower_id not in (
                leader.group_members or []
            )

        await poll_until(is_ungrouped, timeout=3.0)

        # Group follower to leader
        await client.players.group(follower_id, leader_id)

        async def is_grouped():
            await client.players.fetch_state()
            follower = next(p for p in client.players if p.player_id == follower_id)
            leader = next(p for p in client.players if p.player_id == leader_id)
            return follower.synced_to == leader_id or follower_id in (
                leader.group_members or []
            )

        assert await poll_until(is_grouped, timeout=5.0), (
            "Follower should be synced to leader"
        )

        # Ungroup
        await client.players.ungroup(follower_id)

        assert await poll_until(is_ungrouped, timeout=10.0), (
            "Follower should no longer be synced"
        )
