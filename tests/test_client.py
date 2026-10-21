"""Tests for client connection management."""

import asyncio

import pytest
from music_assistant_client.exceptions import (
    CannotConnect,
    ConnectionClosed,
    InvalidState,
)

import music_assistant_mcp.client as client_module
from music_assistant_mcp.client import get_client, tool_errors, with_reconnect


class FakeConnection:
    """Minimal connection stand-in with a `connected` flag."""

    def __init__(self):
        self.connected = True


class FakeClient:
    """Minimal MusicAssistantClient stand-in used by connection tests."""

    instances = 0
    keep_listening = True

    def __init__(self, server_url, aiohttp_session, token):
        type(self).instances += 1
        self.connection = FakeConnection()

    async def start_listening(self, init_ready=None):
        init_ready.set()
        # Stay "connected" until keep_listening flips or the task is cancelled
        while type(self).keep_listening:
            await asyncio.sleep(0.01)

    async def disconnect(self):
        self.connection.connected = False


@pytest.fixture(autouse=True)
async def fresh_connection_state(monkeypatch):
    """Isolate module-level connection state and fake client accounting per test."""
    monkeypatch.setenv("MUSIC_ASSISTANT_URL", "http://test:8095")
    monkeypatch.setenv("MUSIC_ASSISTANT_TOKEN", "token")
    FakeClient.instances = 0
    FakeClient.keep_listening = True
    client_module._connection = None
    client_module._connection_lock = asyncio.Lock()
    yield
    if client_module._connection is not None:
        await client_module._connection.disconnect()
    client_module._connection = None


@pytest.mark.asyncio
async def test_get_client_concurrent_calls_connect_once(monkeypatch):
    """Concurrent get_client() calls share a single connection attempt."""
    monkeypatch.setattr(client_module, "MusicAssistantClient", FakeClient)

    clients = await asyncio.gather(*(get_client() for _ in range(5)))

    assert len({id(c) for c in clients}) == 1
    assert FakeClient.instances == 1


@pytest.mark.asyncio
async def test_get_client_reconnects_when_listener_dies(monkeypatch):
    """A connection whose listener stopped is replaced on the next call."""
    monkeypatch.setattr(client_module, "MusicAssistantClient", FakeClient)

    first = await get_client()
    assert FakeClient.instances == 1

    # Kill the listener task so the connection is no longer alive
    FakeClient.keep_listening = False
    await asyncio.sleep(0.05)

    # A fresh connection starts alive
    FakeClient.keep_listening = True
    second = await get_client()

    assert second is not first
    assert FakeClient.instances == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        CannotConnect(ConnectionError("Connector is closed.")),
        ConnectionClosed("Connection lost"),
        InvalidState("Not connected"),
    ],
)
async def test_with_reconnect_retries_on_client_exceptions(monkeypatch, error):
    """with_reconnect retries once on music_assistant_client exceptions."""
    call_count = 0

    @with_reconnect
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise error
        return "success"

    async def mock_force_reconnect():
        pass

    monkeypatch.setattr(client_module, "force_reconnect", mock_force_reconnect)

    result = await flaky_function()

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_tool_errors_propagates_connection_and_cancellation():
    """tool_errors must not swallow connection errors or cancellation."""

    @with_reconnect
    @tool_errors
    async def cancelled_function():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await cancelled_function()


@pytest.mark.asyncio
async def test_tool_errors_carries_underlying_reason():
    """Unexpected failures surface as ToolError with type and message intact."""
    from mcp.server.mcpserver.exceptions import ToolError

    @tool_errors
    async def boom():
        raise RuntimeError("the real reason")

    with pytest.raises(ToolError, match="RuntimeError: the real reason"):
        await boom()
