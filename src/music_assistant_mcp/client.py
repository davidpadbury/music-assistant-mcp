"""Music Assistant client connection management."""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

from mcp.server.mcpserver.exceptions import ToolError
from music_assistant_client import MusicAssistantClient
from music_assistant_client.exceptions import (
    CannotConnect,
    ConnectionClosed,
    InvalidState,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# How long to wait for the initial state fetch after connecting.
CONNECT_TIMEOUT = 10.0


class MusicAssistantConnection:
    """Manages a single connection to Music Assistant, kept alive by a listener task.

    The underlying MusicAssistantClient runs ``start_listening`` in a background
    task, which owns the websocket read loop and continuously applies incoming
    events to the cached state (players, queues, volumes). Every command is sent
    through that listener, so parallel tool calls never contend for the socket.
    """

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
        self._listener: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        """Whether the listener is still running and the websocket is open."""
        return (
            self._client is not None
            and self._listener is not None
            and not self._listener.done()
            and self._client.connection.connected
        )

    @property
    def client(self) -> MusicAssistantClient:
        """Get the connected client instance."""
        if self._client is None:
            raise RuntimeError(
                "Client not connected. Call connect() first or use get_client()."
            )
        return self._client

    async def connect(self) -> MusicAssistantClient:
        """Establish a connection, or return the existing live one.

        Always builds a fresh MusicAssistantClient: once ``start_listening``
        exits it disconnects itself and cannot be reused.
        """
        if self.is_connected and self._client is not None:
            return self._client

        if self._client is not None:
            # Stale connection - tear it down before building a fresh one
            await self._cleanup()

        return await self._connect_fresh()

    async def reconnect(self) -> MusicAssistantClient:
        """Force a fresh connection: tear down the current one and reconnect."""
        await self._cleanup()
        return await self._connect_fresh()

    async def disconnect(self) -> None:
        """Disconnect from Music Assistant server."""
        await self._cleanup()

    async def _connect_fresh(self) -> MusicAssistantClient:
        client = MusicAssistantClient(
            server_url=self.url,
            aiohttp_session=None,
            token=self.token,
        )
        init_ready = asyncio.Event()
        listener = asyncio.create_task(client.start_listening(init_ready))

        try:
            await asyncio.wait_for(init_ready.wait(), timeout=CONNECT_TIMEOUT)
        except TimeoutError:
            listener.cancel()
            await self._drain(listener)
            await self._quiet_disconnect(client)
            raise CannotConnect(
                TimeoutError(f"Timed out connecting to {self.url}")
            ) from None

        if listener.done():
            # Listener exited before initialization finished
            await self._quiet_disconnect(client)
            exc = listener.exception()
            if exc is not None:
                raise exc
            raise CannotConnect(
                ConnectionError(f"Connection to {self.url} closed during startup")
            ) from None

        self._client = client
        self._listener = listener
        return client

    async def _cleanup(self) -> None:
        """Cancel the listener task and disconnect the client, ignoring errors."""
        if self._listener is not None and not self._listener.done():
            self._listener.cancel()
            await self._drain(self._listener)
        self._listener = None
        if self._client is not None:
            await self._quiet_disconnect(self._client)
        self._client = None

    @staticmethod
    async def _drain(task: asyncio.Task) -> None:
        """Await a task, swallowing its result, errors, and cancellation."""
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110 - draining a task
            pass

    @staticmethod
    async def _quiet_disconnect(client: MusicAssistantClient) -> None:
        try:
            await client.disconnect()
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            logger.debug("Error during disconnect cleanup: %s", exc)


# Global connection instance (lazy initialization)
_connection: MusicAssistantConnection | None = None
# Serializes connection creation/reconnect so concurrent callers share one attempt
_connection_lock = asyncio.Lock()


async def get_client() -> MusicAssistantClient:
    """Get or create the Music Assistant client connection.

    This is the main entry point for tools to get a connected client.
    The connection is established on first use and reused for subsequent calls.
    If the connection has dropped, it will automatically reconnect.
    """
    global _connection

    async with _connection_lock:
        if _connection is None:
            _connection = MusicAssistantConnection()

        # Check if existing connection is still alive, reconnect if not
        if not _connection.is_connected:
            await _connection.connect()

        return _connection.client


async def force_reconnect() -> MusicAssistantClient:
    """Force a fresh connection to Music Assistant.

    Disconnects any existing connection and establishes a new one.
    Used when the existing connection is detected to be stale.
    """
    global _connection

    async with _connection_lock:
        if _connection is None:
            _connection = MusicAssistantConnection()
        return await _connection.reconnect()


# Exceptions that indicate a stale/broken connection
CONNECTION_ERRORS = (
    ConnectionResetError,  # "Cannot write to closing transport"
    ConnectionError,
    BrokenPipeError,
    OSError,  # Catches various network-related errors
    CannotConnect,  # "Connector is closed."
    ConnectionClosed,  # websocket dropped
    InvalidState,  # "Not connected"
)


def with_reconnect(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Decorator that retries a function once after reconnecting on connection errors.

    Use this to wrap MCP tool functions. If the function raises a connection error
    (e.g., "Cannot write to closing transport"), this will force a reconnection
    and retry the function once.

    The decorated function should call get_client() to get the client, so that
    on retry it gets the fresh connection.

    Example:
        @with_reconnect
        async def my_tool():
            client = await get_client()
            return await client.players.volume_set(...)
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except CONNECTION_ERRORS as e:
            logger.warning(
                f"Connection error in {getattr(func, '__name__', repr(func))}, reconnecting: {e}"
            )
            await force_reconnect()
            # Retry once - the function will call get_client() again
            return await func(*args, **kwargs)

    return wrapper


def tool_errors(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Turn unexpected tool failures into ToolError carrying the underlying reason.

    The MCP SDK deliberately strips the message from unhandled crashes, so the
    client would otherwise see a bare 'Error executing tool <name>' with no
    detail. Connection errors and deliberate ToolError pass through so
    with_reconnect can retry and validation errors keep their own text.
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except (ToolError, asyncio.CancelledError, *CONNECTION_ERRORS):
            raise
        except Exception as exc:
            raise ToolError(f"{type(exc).__name__}: {exc}") from exc

    return wrapper
