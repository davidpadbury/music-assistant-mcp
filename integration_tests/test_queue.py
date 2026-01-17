"""Integration tests for queue tools."""

from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import RepeatMode


class TestQueueState:
    """Tests for ma_queue functionality."""

    async def test_get_queue(self, client: MusicAssistantClient, player_id: str):
        """Get queue returns queue object."""
        await client.player_queues.fetch_state()
        queue = next(
            (q for q in client.player_queues if q.queue_id == player_id),
            None,
        )
        # Queue should exist for any valid player
        assert queue is not None, f"No queue found for player {player_id}"

    async def test_queue_has_settings(
        self, client: MusicAssistantClient, player_id: str
    ):
        """Queue has shuffle and repeat settings."""
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        assert hasattr(queue, "shuffle_enabled"), "Queue missing shuffle_enabled"
        assert hasattr(queue, "repeat_mode"), "Queue missing repeat_mode"

    async def test_set_shuffle(self, client: MusicAssistantClient, player_id: str):
        """Can enable and disable shuffle."""
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        original_shuffle = queue.shuffle_enabled

        # Toggle shuffle
        await client.player_queues.shuffle(player_id, not original_shuffle)
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        assert queue.shuffle_enabled != original_shuffle

        # Restore original
        await client.player_queues.shuffle(player_id, original_shuffle)

    async def test_set_repeat(self, client: MusicAssistantClient, player_id: str):
        """Can set repeat mode."""
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        original_repeat = queue.repeat_mode

        # Set to repeat all
        await client.player_queues.repeat(player_id, RepeatMode.ALL)
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        assert queue.repeat_mode == RepeatMode.ALL

        # Set to repeat off
        await client.player_queues.repeat(player_id, RepeatMode.OFF)
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)
        assert queue.repeat_mode == RepeatMode.OFF

        # Restore original
        await client.player_queues.repeat(player_id, original_repeat)

    async def test_clear_queue(self, client: MusicAssistantClient, player_id: str):
        """Clear queue command executes without error."""
        # Note: This is destructive but the queue might already be empty
        await client.player_queues.clear(player_id)

    async def test_queue_items_attribute(
        self, client: MusicAssistantClient, player_id: str
    ):
        """Queue items attribute is iterable when present."""
        await client.player_queues.fetch_state()
        queue = next(q for q in client.player_queues if q.queue_id == player_id)

        items = getattr(queue, "items", None)
        # items might be None, an int, or a list depending on queue state
        # This test documents the actual behavior
        if items is not None and not isinstance(items, int):
            # If it's a list, verify we can iterate it
            assert hasattr(items, "__iter__"), "Queue items should be iterable"


class TestTransferQueue:
    """Tests for ma_transfer_queue functionality."""

    async def test_transfer_queue(
        self, client: MusicAssistantClient, two_player_ids: tuple[str, str]
    ):
        """Transfer queue executes without error."""
        source_id, target_id = two_player_ids
        # Transfer from source to target (may be no-op if queue is empty)
        await client.player_queues.transfer_queue(source_id, target_id)
