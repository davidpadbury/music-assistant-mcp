"""Music Assistant client connection management."""

import os

from music_assistant_client import MusicAssistantClient


class MusicAssistantConnection:
    """Manages connection to Music Assistant server."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
    ):
        resolved_url = url or os.environ.get("MUSIC_ASSISTANT_URL")
        if not resolved_url:
            raise ValueError(
                "Music Assistant URL required. "
                "Set MUSIC_ASSISTANT_URL environment variable or pass url parameter."
            )

        self.url: str = resolved_url
        self.token = token or os.environ.get("MUSIC_ASSISTANT_TOKEN")
        self._client: MusicAssistantClient | None = None

    async def connect(self) -> MusicAssistantClient:
        """Establish connection to Music Assistant server."""
        if self._client is not None:
            return self._client

        # Token is passed to constructor (required for schema 28+)
        self._client = MusicAssistantClient(
            server_url=self.url,
            aiohttp_session=None,
            token=self.token,
        )
        await self._client.connect()

        # Fetch initial state for players and queues
        await self._client.players.fetch_state()
        await self._client.player_queues.fetch_state()

        return self._client

    @property
    def client(self) -> MusicAssistantClient:
        """Get the connected client instance."""
        if self._client is None:
            raise RuntimeError(
                "Client not connected. Call connect() first or use get_client()."
            )
        return self._client

    async def disconnect(self) -> None:
        """Disconnect from Music Assistant server."""
        if self._client:
            await self._client.disconnect()
            self._client = None


# Global connection instance (lazy initialization)
_connection: MusicAssistantConnection | None = None


async def get_client() -> MusicAssistantClient:
    """Get or create the Music Assistant client connection.

    This is the main entry point for tools to get a connected client.
    The connection is established on first use and reused for subsequent calls.
    If the connection has dropped, it will automatically reconnect.
    """
    global _connection

    if _connection is None:
        _connection = MusicAssistantConnection()

    # Check if existing connection is still alive
    if _connection._client is None or not _connection._client.connection.connected:
        if _connection._client is not None:
            # Clean up stale connection
            await _connection.disconnect()
        await _connection.connect()

    return _connection.client
