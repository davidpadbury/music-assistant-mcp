"""Integration tests for playback tools."""

import pytest
from music_assistant_client import MusicAssistantClient
from music_assistant_models.errors import MediaNotFoundError


class TestPlaybackControl:
    """Tests for ma_playback functionality."""

    async def test_pause(self, client: MusicAssistantClient, player_id: str):
        """Pause command executes without error."""
        # Pause should work regardless of current state
        await client.player_queues.pause(player_id)
        # No assertion needed - if it doesn't raise, it worked

    async def _queue_is_empty(
        self, client: MusicAssistantClient, player_id: str
    ) -> bool:
        """Check whether the player's queue has any items."""
        queue = next((q for q in client.player_queues if q.queue_id == player_id), None)
        return queue is None or not queue.items

    async def test_play(self, client: MusicAssistantClient, player_id: str):
        """Play command executes without error."""
        if await self._queue_is_empty(client, player_id):
            pytest.skip("Queue is empty - cannot verify play")
        await client.player_queues.play(player_id)

    async def test_stop(self, client: MusicAssistantClient, player_id: str):
        """Stop command executes without error."""
        await client.player_queues.stop(player_id)

    async def test_toggle(self, client: MusicAssistantClient, player_id: str):
        """Toggle play/pause executes without error."""
        if await self._queue_is_empty(client, player_id):
            pytest.skip("Queue is empty - cannot verify toggle")
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
        with pytest.raises(MediaNotFoundError):
            await client.player_queues.play_media(
                queue_id=player_id,
                media=["invalid://not-a-real-uri"],
            )
