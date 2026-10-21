"""Tests for MCP tools registration."""

import pytest
from mcp.server.mcpserver import MCPServer

from music_assistant_mcp.client import with_reconnect
from music_assistant_mcp.tools import music, playback, players, queue


async def mock_get_client():
    """Mock client getter that raises - used only for tool registration."""
    raise NotImplementedError("Mock client")


def test_player_tools_register():
    """Test that player tools register correctly."""
    mcp = MCPServer("test")
    players.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_list_players" in tool_names
    assert "ma_volume" in tool_names
    assert "ma_group_volume" in tool_names
    assert "ma_group" in tool_names
    assert "ma_announce" in tool_names
    assert "ma_select_source" in tool_names


def test_playback_tools_register():
    """Test that playback tools register correctly."""
    mcp = MCPServer("test")
    playback.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_playback" in tool_names
    assert "ma_play_media" in tool_names


def test_queue_tools_register():
    """Test that queue tools register correctly."""
    mcp = MCPServer("test")
    queue.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_queue" in tool_names
    assert "ma_queue_item" in tool_names
    assert "ma_transfer_queue" in tool_names


def test_music_tools_register():
    """Test that music tools register correctly."""
    mcp = MCPServer("test")
    music.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_search" in tool_names
    assert "ma_browse" in tool_names


def test_all_tools_register():
    """Test that all 13 tools register without conflict."""
    mcp = MCPServer("test")
    players.register_tools(mcp, mock_get_client)
    playback.register_tools(mcp, mock_get_client)
    queue.register_tools(mcp, mock_get_client)
    music.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert len(tool_names) == 13

    expected_tools = [
        "ma_list_players",
        "ma_volume",
        "ma_group_volume",
        "ma_group",
        "ma_announce",
        "ma_select_source",
        "ma_playback",
        "ma_play_media",
        "ma_queue",
        "ma_queue_item",
        "ma_transfer_queue",
        "ma_search",
        "ma_browse",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Missing tool: {tool}"


@pytest.mark.asyncio
async def test_format_queue_state_fetches_items_from_api():
    """Test that format_queue_state fetches items via API, not from queue.items.
    The queue.items attribute is an int (count), not a list. This test ensures
    we call get_queue_items() to fetch actual items.
    """

    class StubQueue:
        queue_id = "test_queue"
        items = 2  # This is a COUNT, not a list!
        shuffle_enabled = False
        repeat_mode = "off"
        current_item = None

    class StubPlayerQueues:
        def __iter__(self):
            return iter([StubQueue()])

        async def get_queue_items(
            self, queue_id: str, limit: int = 500, offset: int = 0
        ):
            class Item:
                def __init__(self, name, queue_item_id):
                    self.name = name
                    self.queue_item_id = queue_item_id

            return [Item("Track One", "item_1"), Item("Track Two", "item_2")]

    payload = await queue.build_queue_payload(StubPlayerQueues(), "test_queue")
    result = queue.format_queue_state(payload)

    assert "Track One" in result
    assert "Track Two" in result
    assert "item_1" in result
    assert payload["total_items"] == 2
    assert payload["items"][0]["name"] == "Track One"
    assert payload["items"][0]["queue_item_id"] == "item_1"


def test_player_payload_extracts_structured_fields():
    """Player payload has machine-readable fields and text renders from them."""
    from types import SimpleNamespace as NS

    player = NS(
        player_id="p1",
        name="Kitchen",
        available=True,
        volume_level=42,
        volume_muted=False,
        playback_state=NS(value="playing"),
        group_members=[],
        synced_to=None,
        active_source="src1",
        source_list=[NS(id="src1", name="TV Input")],
    )
    payload = players._player_payload(player)
    assert payload["player_id"] == "p1"
    assert payload["volume_level"] == 42
    assert payload["state"] == "playing"
    assert payload["active_source_name"] == "TV Input"
    assert payload["group_members"] == []

    text = players._format_players([payload])
    assert "Kitchen" in text
    assert "Volume: 42%" in text
    assert "State: playing" in text


def test_search_payload_splits_name_and_uri():
    """Search payload separates name, uri, and artist fields (not one blob)."""
    from types import SimpleNamespace as NS

    results = NS(
        artists=[],
        albums=[
            NS(name="Abbey Road", uri="apple://album/1", artists=[NS(name="Beatles")])
        ],
        tracks=[
            NS(
                name="Yesterday",
                uri="apple://track/9",
                artists=[NS(name="Beatles")],
                album=NS(name="Help!"),
            )
        ],
        playlists=[],
        radio=[],
    )

    payload = music._search_payload("beatles", results, limit=10)
    track = payload["tracks"][0]
    assert track["name"] == "Yesterday"
    assert track["uri"] == "apple://track/9"
    assert track["artists"] == ["Beatles"]
    assert track["album"] == "Help!"

    text = music._format_search(payload)
    assert "Yesterday" in text
    assert "apple://track/9" in text


def test_browse_payload_separates_folders_and_media():
    """Browse payload keeps navigable paths and media URIs in distinct fields."""
    from types import SimpleNamespace as NS

    items = [
        NS(
            name="Albums",
            uri="spotify://folder/albums",
            media_type="folder",
            is_folder=True,
        ),
        NS(
            name="Thriller",
            uri="spotify://album/1",
            media_type="album",
            is_folder=False,
        ),
    ]
    payload = music._browse_payload("spotify://folder/albums", items, 0, 20)
    assert payload["folders"] == [
        {"name": "Albums", "path": "spotify://albums", "type": "folder"}
    ]
    assert payload["media"] == [
        {"name": "Thriller", "uri": "spotify://album/1", "type": "album"}
    ]

    text = music._format_browse(payload)
    assert "spotify://albums" in text
    assert "Thriller" in text


@pytest.mark.asyncio
async def test_with_reconnect_retries_on_connection_error(monkeypatch):
    """Test that with_reconnect decorator retries after ConnectionResetError."""
    call_count = 0

    @with_reconnect
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionResetError("Cannot write to closing transport")
        return "success"

    # Mock force_reconnect to avoid actual connection
    async def mock_force_reconnect():
        pass

    monkeypatch.setattr(
        "music_assistant_mcp.client.force_reconnect", mock_force_reconnect
    )

    result = await flaky_function()

    assert result == "success"
    assert call_count == 2  # First call failed, retry succeeded


@pytest.mark.asyncio
async def test_with_reconnect_passes_through_on_success():
    """Test that with_reconnect passes through when no error occurs."""
    call_count = 0

    @with_reconnect
    async def working_function():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await working_function()

    assert result == "success"
    assert call_count == 1  # Only called once


@pytest.mark.asyncio
async def test_with_reconnect_propagates_non_connection_errors():
    """Test that with_reconnect doesn't retry for non-connection errors."""

    @with_reconnect
    async def error_function():
        raise ValueError("Not a connection error")

    with pytest.raises(ValueError, match="Not a connection error"):
        await error_function()
