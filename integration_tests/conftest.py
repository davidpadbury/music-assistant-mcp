"""Pytest fixtures for integration tests."""

import asyncio
import os
import time
from collections.abc import Awaitable, Callable

import pytest
from music_assistant_client import MusicAssistantClient

from music_assistant_mcp.client import MusicAssistantConnection


async def poll_until(
    condition: Callable[[], Awaitable[bool]],
    timeout: float = 5.0,
    interval: float = 0.3,
) -> bool:
    """Poll until condition returns True or timeout is reached.

    Args:
        condition: Async callable that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Time between polls in seconds

    Returns:
        True if condition was met, False if timeout was reached
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if await condition():
            return True
        await asyncio.sleep(interval)
    return False


def _get_env_or_skip(name: str) -> str:
    """Get environment variable or skip test."""
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} environment variable not set")
    return value


@pytest.fixture
def ma_url() -> str:
    """Get Music Assistant URL from environment."""
    return _get_env_or_skip("MUSIC_ASSISTANT_URL")


@pytest.fixture
def ma_token() -> str | None:
    """Get Music Assistant token from environment (optional)."""
    return os.environ.get("MUSIC_ASSISTANT_TOKEN")


@pytest.fixture
async def client(ma_url: str, ma_token: str | None) -> MusicAssistantClient:
    """Create a connected Music Assistant client for each test."""
    connection = MusicAssistantConnection(url=ma_url, token=ma_token)
    await connection.connect()
    yield connection.client
    await connection.disconnect()


@pytest.fixture
async def player_id(client: MusicAssistantClient) -> str:
    """Get the first available player ID, or skip if none available."""
    players = list(client.players)
    if not players:
        pytest.skip("No players available")
    return players[0].player_id


@pytest.fixture
async def two_player_ids(client: MusicAssistantClient) -> tuple[str, str]:
    """Get two player IDs for grouping tests, or skip if fewer than 2 available."""
    players = list(client.players)
    if len(players) < 2:
        pytest.skip("At least 2 players required for grouping tests")
    return players[0].player_id, players[1].player_id


@pytest.fixture
async def player_volume(client: MusicAssistantClient, player_id: str) -> int:
    """Get current volume of the first player, to restore after tests."""
    for player in client.players:
        if player.player_id == player_id:
            return player.volume_level
    return 50  # Default fallback
