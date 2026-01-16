"""Music Assistant client connection management."""

import os
from typing import Optional

from music_assistant_client import MusicAssistantClient


class MusicAssistantConnection:
    """Manages connection to Music Assistant server."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.url = url or os.environ.get("MUSIC_ASSISTANT_URL")
        self.token = token or os.environ.get("MUSIC_ASSISTANT_TOKEN")
        self._client: Optional[MusicAssistantClient] = None

        if not self.url:
            raise ValueError(
                "Music Assistant URL required. Set MUSIC_ASSISTANT_URL environment variable "
                "or pass url parameter."
            )

    async def connect(self) -> MusicAssistantClient:
        """Establish connection to Music Assistant server."""
        if self._client is not None:
            return self._client

        self._client = MusicAssistantClient(self.url, None)

        # Connect with token if provided (required for schema 28+)
        if self.token:
            await self._client.connect(token=self.token)
        else:
            await self._client.connect()

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
_connection: Optional[MusicAssistantConnection] = None


async def get_client() -> MusicAssistantClient:
    """Get or create the Music Assistant client connection.

    This is the main entry point for tools to get a connected client.
    The connection is established on first use and reused for subsequent calls.
    """
    global _connection

    if _connection is None:
        _connection = MusicAssistantConnection()

    if _connection._client is None:
        await _connection.connect()

    return _connection.client
