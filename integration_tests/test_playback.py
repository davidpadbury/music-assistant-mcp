"""Integration tests for playback tools."""

import pytest
from music_assistant_client import MusicAssistantClient


class TestPlaybackControl:
    """Tests for ma_playback functionality."""

    async def test_pause(self, client: MusicAssistantClient, player_id: str):
        """Pause command executes without error."""
        # Pause should work regardless of current state
        await client.player_queues.pause(player_id)
        # No assertion needed - if it doesn't raise, it worked

    async def test_play(self, client: MusicAssistantClient, player_id: str):
        """Play command executes without error."""
        await client.player_queues.play(player_id)

    async def test_stop(self, client: MusicAssistantClient, player_id: str):
        """Stop command executes without error."""
        await client.player_queues.stop(player_id)

    async def test_toggle(self, client: MusicAssistantClient, player_id: str):
        """Toggle play/pause executes without error."""
        await client.player_queues.play_pause(player_id)


class TestPlayMedia:
    """Tests for ma_play_media functionality.

    Note: These tests are more limited because they require actual media URIs.
    The search tests verify we can find URIs; these tests verify the play_media
    API accepts them.
    """

    async def test_play_media_invalid_uri_raises(
        self, client: MusicAssistantClient, player_id: str
    ):
        """Playing an invalid URI raises an appropriate error."""
        with pytest.raises(Exception):
            await client.player_queues.play_media(
                queue_id=player_id,
                media=["invalid://not-a-real-uri"],
            )
